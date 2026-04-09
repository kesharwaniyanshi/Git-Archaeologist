import structlog
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Dict

from core.models.api import LinkRepoRequest, RepositoryResponse
from db.models import Repository
from api.dependencies import get_db, get_current_user
from core.github_fetcher import ingest_repository_task

logger = structlog.get_logger()
router = APIRouter() 

@router.post("/repos/link", response_model=RepositoryResponse)
async def link_repository(
    request: LinkRepoRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    url = request.url.strip()
    # Normalize github shortlinks flawlessly into robust explicit paths
    if not url.startswith("https://github.com/"):
        url = f"https://github.com/{url}" 
        
    parts = url.replace("https://github.com/", "").split("/")
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub URL. Must explicitly follow owner/repo shape.")
        
    owner = parts[0]
    name = parts[1].replace(".git", "")
    final_url = f"https://github.com/{owner}/{name}"
    
    repo = db.query(Repository).filter(Repository.url == final_url).first()
    if not repo:
        repo = Repository(url=final_url, owner=owner, name=name)
        db.add(repo)
        db.commit()
        db.refresh(repo)
        
    # Fire off background ingestion safely to prevent blocking the HTTP request!
    # By dropping this uniformly into FastAPI's native BackgroundTasks loop, the user returns a 200 immediately
    # while the engine rips the commit diffs linearly utilizing PyDriller inside ThreadPool limits!
    background_tasks.add_task(ingest_repository_task, repo.id)
    
    return RepositoryResponse(
        id=repo.id,
        url=repo.url,
        owner=repo.owner,
        name=repo.name,
        last_indexed_commit=repo.last_indexed_commit,
        created_at=str(repo.created_at)
    )
