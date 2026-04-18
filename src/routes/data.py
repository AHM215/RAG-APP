import os

from fastapi import APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
from models import ChunkModel, ProjectModel, AssetModel
from models.enums.AssetTypeEnum import AssetTypeEnum
from models import DataChunk, Asset
from helpers.config import get_settings, Settings
from controllers import DataController, ProcessController
from schemas.data import ProcessRequest
import aiofiles
from models import ResponseSignal
import logging

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"],
)

@data_router.post("/upload/{project_id}")
async def upload_data(request: Request, project_id: str, file: UploadFile,
                      app_settings: Settings = Depends(get_settings)):
    

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    # validate the file properties
    data_controller = DataController()

    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)

    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": result_signal
            }
        )

    file_path, file_id = data_controller.generate_unique_filepath(
        orig_file_name=file.filename,
        project_id=project_id
    )

    try:
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_DEFAULT_CHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:

        logger.error(f"Error while uploading file: {e}")

        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.FILE_UPLOAD_FAILED.value
            }
        )
    
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    asset_record = Asset(
        asset_project_id=project.id,
        asset_name=file_id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_size=os.path.getsize(file_path)
    )
    asset_record = await asset_model.create_asset(asset_record)


    return JSONResponse(
            content={
                "signal": ResponseSignal.FILE_UPLOAD_SUCCESS.value,
                "file_id": str(asset_record.inserted_id)
            }
        )


@data_router.post("/process/{project_id}")
async def process_endpoint(request: Request, project_id: str, process_request: ProcessRequest):

    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    process_controller = ProcessController(project_id=project_id)

    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)

    if process_request.do_reset == 1:
        deleted_records = await chunk_model.delete_chunks_by_project_id(project_id=project.id)
        logger.info(f"Reset done for project_id: {deleted_records} chunks deleted")


    asset_model = await AssetModel.create_instance(db_client=request.app.db_client) 

    project_files_ids = {}
    if process_request.file_id:
        ##### get the asset name and file id
        asset_record = await asset_model.get_asset_record(asset_project_id=project.id, asset_name=process_request.file_id)
        if not asset_record:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "signal": ResponseSignal.FILE_NOT_FOUND.value
                }
            )
        project_files_ids = {asset_record.id: asset_record.asset_name}
    else:
        project_assets = await asset_model.get_all_project_assets(asset_project_id=project.id, asset_type=AssetTypeEnum.FILE.value)
        project_files_ids = {asset.id:asset.asset_name for asset in project_assets}

    if len(project_files_ids) == 0:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal": ResponseSignal.NO_FILES_TO_PROCESS.value
            }
        )
    
    no_records = 0
    no_files = 0
    for asset_id, file_id in project_files_ids.items():
        file_content = process_controller.get_file_content(file_id=file_id)
        if isinstance(file_content, JSONResponse):
            logger.error(f"Error while loading file content for file_id: {file_id} with error: {file_content.body}")
            continue

        if isinstance(file_content, JSONResponse):
            return file_content

        file_chunks = process_controller.process_file_content(
            file_content=file_content,
            file_id=file_id,
            chunk_size=process_request.chunk_size,
            overlap_size=process_request.overlap_size
        )

        file_cunks_records = [
            DataChunk(
                chunk_text=chunk.page_content,
                chunk_metadata=chunk.metadata,
                chunk_order=idx + 1,
                chunk_project_id=project.id,
                chunk_asset_id=asset_id
            ) for idx, chunk in enumerate(file_chunks)  
        ]

        no_records += await chunk_model.insert_many_chunks(file_cunks_records)
        no_files += 1

    

    return JSONResponse(
        content={
            "signal": ResponseSignal.PROCESSING_SUCCESS.value,
            "inserted_chunks": no_records,
            "processed_files": no_files
        }
    )

