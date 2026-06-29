from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.core.config import get_settings
from app.core.response import maybe_wrap
from app.services.document_service import DocumentInput, DocumentService

# 文档导入相关路由，前缀 /document
router = APIRouter(prefix="/document", tags=["document"])


@router.post("/import")
async def import_document(
    text: str,
    source: str = "manual",
    doc_name: str | None = None,
    version: str = "1.0",
    request: Request = None,
):
    """通过文本字符串导入文档

    兼容旧接口，支持直接传入文本内容。
    如果提供了 doc_name 则走新入口，否则走旧入口兼容逻辑。

    Args:
        text:     待导入的文本内容（必填）
        source:   文档来源类型，默认 "manual"
        doc_name: 文档名称（可选，不传则自动生成）
        version:  文档版本号，默认 "1.0"
        request:  FastAPI 请求对象，用于网关响应包装

    Returns:
        导入结果，包含 doc_id、imported_chunks、status 等字段
    """
    service = DocumentService(get_settings())
    try:
        # 如果传了 doc_name，走统一标准入口
        if doc_name:
            doc_input = DocumentInput(
                doc_name=doc_name,
                source_type=source,
                raw_text=text,
                version=version,
            )
            result = service.import_document(doc_input)
        else:
            # 否则走兼容旧接口
            result = service.import_text(text=text, source=source)
    except ValueError as exc:
        # 参数校验失败（如空文本），返回 400
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        # 其他异常（如 Chroma 写入失败），返回 500
        raise HTTPException(status_code=500, detail=f"文档导入失败: {exc}") from exc

    # 如果经过网关，进行统一响应包装
    return maybe_wrap(request, result) if request else result


@router.post("/upload")
async def upload_document(
    file: UploadFile,
    source: str = "upload",
    version: str = "1.0",
    request: Request = None,
):
    """通过上传文件导入文档（支持 .txt 文件）

    读取文件内容后，转为标准 DocumentInput 对象进入处理链路。
    优先使用 UTF-8 解码，失败则回退到 GBK 编码。

    Args:
        file:    上传的文件对象（FastAPI UploadFile）
        source:  文档来源类型，默认 "upload"
        version: 文档版本号，默认 "1.0"
        request: FastAPI 请求对象，用于网关响应包装

    Returns:
        导入结果，包含 doc_id、imported_chunks、status 等字段
    """
    # 文件名不能为空
    if not file.filename:
        raise HTTPException(status_code=400, detail="文件名为空")

    # 读取文件内容
    content = await file.read()
    # 优先 UTF-8 解码，失败时尝试 GBK（常见于 Windows 中文文件）
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        text = content.decode("gbk", errors="replace")

    # 转为标准导入对象
    doc_input = DocumentInput(
        doc_name=file.filename,          # 使用文件名作为文档名称
        source_type=source,
        source_path=file.filename,       # 记录原始文件路径
        raw_text=text,
        version=version,
    )

    service = DocumentService(get_settings())
    try:
        result = service.import_document(doc_input)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文档导入失败: {exc}") from exc

    return maybe_wrap(request, result) if request else result
