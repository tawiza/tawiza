"""
Prompts Management API

Endpoints pour gérer les templates de prompts dynamiques.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from pydantic import BaseModel, Field

from src.infrastructure.prompts import (
    PromptFormat,
    PromptManager,
    get_prompt_manager,
)

router = APIRouter()


# Pydantic models
class PromptTemplateCreate(BaseModel):
    """Request model for creating a prompt template."""

    name: str = Field(..., min_length=1, max_length=100)
    format: PromptFormat
    template: str = Field(..., min_length=1)
    description: str = ""
    version: str = "1.0"
    metadata: dict = {}


class PromptTemplateResponse(BaseModel):
    """Response model for prompt template."""

    name: str
    format: str
    template: str
    variables: list[str]
    description: str
    version: str
    usage_count: int
    metadata: dict
    created_at: str
    updated_at: str


class PromptRenderRequest(BaseModel):
    """Request model for rendering a prompt."""

    template_name: str
    variables: dict = Field(default_factory=dict)


class PromptRenderResponse(BaseModel):
    """Response model for rendered prompt."""

    template_name: str
    rendered_prompt: str
    variables_used: dict


class PromptStatsResponse(BaseModel):
    """Response model for prompt statistics."""

    total_renders: int
    total_templates: int
    renders_by_template: dict
    renders_by_format: dict
    templates_by_format: dict


@router.post(
    "/templates",
    response_model=PromptTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create prompt template",
    description="Create a new prompt template with variables",
)
async def create_template(
    request: PromptTemplateCreate, manager: PromptManager = Depends(get_prompt_manager)
) -> PromptTemplateResponse:
    """
    Create a new prompt template.

    Args:
        request: Template creation request
        manager: Prompt manager instance

    Returns:
        Created template

    Example:
        ```json
        {
            "name": "my_template",
            "format": "browser",
            "template": "Navigate to {url} and do {action}",
            "description": "My custom template",
            "version": "1.0"
        }
        ```
    """
    try:
        template = manager.register_template(
            name=request.name,
            format=request.format,
            template=request.template,
            description=request.description,
            version=request.version,
            metadata=request.metadata,
        )

        # Save templates after creation
        manager.save_templates()

        return PromptTemplateResponse(**template.to_dict())

    except Exception as e:
        logger.error(f"Failed to create template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create template: {str(e)}",
        )


@router.get(
    "/templates",
    response_model=list[PromptTemplateResponse],
    summary="List prompt templates",
    description="List all registered prompt templates",
)
async def list_templates(
    format_filter: PromptFormat | None = None, manager: PromptManager = Depends(get_prompt_manager)
) -> list[PromptTemplateResponse]:
    """
    List all prompt templates, optionally filtered by format.

    Args:
        format_filter: Optional format filter
        manager: Prompt manager instance

    Returns:
        List of templates
    """
    templates = manager.list_templates(format_filter=format_filter)
    return [PromptTemplateResponse(**t.to_dict()) for t in templates]


@router.get(
    "/templates/{template_name}",
    response_model=PromptTemplateResponse,
    summary="Get prompt template",
    description="Get a specific prompt template by name",
)
async def get_template(
    template_name: str, manager: PromptManager = Depends(get_prompt_manager)
) -> PromptTemplateResponse:
    """
    Get a specific prompt template.

    Args:
        template_name: Template name
        manager: Prompt manager instance

    Returns:
        Template details

    Raises:
        HTTPException: If template not found
    """
    template = manager.get_template(template_name)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_name}' not found"
        )

    return PromptTemplateResponse(**template.to_dict())


@router.post(
    "/render",
    response_model=PromptRenderResponse,
    summary="Render prompt template",
    description="Render a prompt template with variables",
)
async def render_template(
    request: PromptRenderRequest, manager: PromptManager = Depends(get_prompt_manager)
) -> PromptRenderResponse:
    """
    Render a prompt template with provided variables.

    Args:
        request: Render request with template name and variables
        manager: Prompt manager instance

    Returns:
        Rendered prompt

    Raises:
        HTTPException: If template not found or variables missing

    Example:
        ```json
        {
            "template_name": "browser_navigation",
            "variables": {
                "url": "https://google.com",
                "action": "search for Python tutorials"
            }
        }
        ```
    """
    try:
        rendered = manager.render(request.template_name, **request.variables)

        return PromptRenderResponse(
            template_name=request.template_name,
            rendered_prompt=rendered,
            variables_used=request.variables,
        )

    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to render template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to render template: {str(e)}",
        )


@router.get(
    "/stats",
    response_model=PromptStatsResponse,
    summary="Get prompt statistics",
    description="Get statistics about prompt usage",
)
async def get_stats(manager: PromptManager = Depends(get_prompt_manager)) -> PromptStatsResponse:
    """
    Get prompt usage statistics.

    Args:
        manager: Prompt manager instance

    Returns:
        Statistics
    """
    stats = manager.get_stats()
    return PromptStatsResponse(**stats)


@router.delete(
    "/templates/{template_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete prompt template",
    description="Delete a prompt template by name",
)
async def delete_template(template_name: str, manager: PromptManager = Depends(get_prompt_manager)):
    """
    Delete a prompt template.

    Args:
        template_name: Template name
        manager: Prompt manager instance

    Raises:
        HTTPException: If template not found
    """
    template = manager.get_template(template_name)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Template '{template_name}' not found"
        )

    # Remove template
    del manager.templates[template_name]

    # Save changes
    manager.save_templates()

    logger.info(f"Template deleted: {template_name}")


@router.post(
    "/templates/defaults",
    status_code=status.HTTP_200_OK,
    summary="Create default templates",
    description="Create default prompt templates",
)
async def create_defaults(manager: PromptManager = Depends(get_prompt_manager)) -> dict:
    """
    Create default prompt templates.

    Args:
        manager: Prompt manager instance

    Returns:
        Success message with count
    """
    manager.create_default_templates()
    manager.save_templates()

    return {
        "status": "success",
        "message": "Default templates created",
        "count": len(manager.templates),
    }
