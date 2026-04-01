from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..database import get_db
from ..models import RuleTemplate
from ..schemas.template import TemplateOut

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
def list_templates(category: str | None = None, db: Session = Depends(get_db)):
    q = db.query(RuleTemplate)
    if category:
        q = q.filter(RuleTemplate.category == category)
    return q.order_by(RuleTemplate.category, RuleTemplate.sort_order).all()
