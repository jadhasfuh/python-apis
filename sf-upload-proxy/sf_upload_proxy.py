"""
Salesforce File Upload Proxy Service
Receives files from n8n and uploads them to Salesforce using multipart/form-data
Supports files up to 2GB (Salesforce limit)
"""

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import httpx
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Salesforce Upload Proxy",
    description="Proxy service to upload large files to Salesforce from n8n",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "sf-upload-proxy"}

@app.post("/upload-to-salesforce")
async def upload_to_salesforce(
    file: UploadFile = File(...),
    access_token: str = Form(...),
    instance_url: str = Form(...),
    account_id: str = Form(...),
    title: str = Form(...),
    file_name: str = Form(None),
):
    try:
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        actual_filename = file_name or file.filename or f"{title}.pdf"
        
        logger.info(f"Uploading file: {actual_filename} ({file_size_mb:.2f} MB) to Account: {account_id}")
        
        entity_content = json.dumps({
            "Title": title,
            "PathOnClient": actual_filename
        })
        
        files = {
            'entity_content': (None, entity_content, 'application/json'),
            'VersionData': (actual_filename, file_content, file.content_type or 'application/octet-stream')
        }
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            logger.info("Creating ContentVersion...")
            cv_response = await client.post(
                f"{instance_url}/services/data/v59.0/sobjects/ContentVersion",
                headers=headers,
                files=files
            )
            
            if cv_response.status_code != 201:
                logger.error(f"ContentVersion creation failed: {cv_response.text}")
                raise HTTPException(status_code=cv_response.status_code, detail=f"Salesforce error: {cv_response.text}")
            
            cv_id = cv_response.json()['id']
            logger.info(f"ContentVersion created: {cv_id}")
            
            cv_detail_response = await client.get(
                f"{instance_url}/services/data/v59.0/sobjects/ContentVersion/{cv_id}",
                headers=headers
            )
            
            if cv_detail_response.status_code != 200:
                raise HTTPException(status_code=cv_detail_response.status_code, detail=f"Failed to get ContentVersion: {cv_detail_response.text}")
            
            content_document_id = cv_detail_response.json()['ContentDocumentId']
            logger.info(f"ContentDocumentId: {content_document_id}")
            
            link_data = {
                "ContentDocumentId": content_document_id,
                "LinkedEntityId": account_id,
                "ShareType": "V",
                "Visibility": "AllUsers"
            }
            
            link_response = await client.post(
                f"{instance_url}/services/data/v59.0/sobjects/ContentDocumentLink",
                headers={**headers, 'Content-Type': 'application/json'},
                json=link_data
            )
            
            link_id = link_response.json()['id'] if link_response.status_code == 201 else None
            if not link_id:
                logger.warning(f"ContentDocumentLink failed: {link_response.text}")
            
            return {
                "success": True,
                "contentVersionId": cv_id,
                "contentDocumentId": content_document_id,
                "contentDocumentLinkId": link_id,
                "fileName": actual_filename,
                "fileSizeMB": round(file_size_mb, 2)
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5051)
