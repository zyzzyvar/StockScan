from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from ..models import Scheme, Rule
from ..schemas.scheme import SchemeCreate, SchemeUpdate, SchemeOut, SchemeListOut, RuleCreate, RuleUpdate, RuleOut, ReorderRequest

router = APIRouter(prefix="/api/schemes", tags=["schemes"])


@router.get("", response_model=list[SchemeListOut])
def list_schemes(db: Session = Depends(get_db)):
    schemes = db.query(Scheme).order_by(Scheme.is_builtin.desc(), Scheme.created_at).all()
    result = []
    for s in schemes:
        d = SchemeListOut.model_validate(s)
        d.rule_count = len(s.rules)
        result.append(d)
    return result


@router.post("", response_model=SchemeOut, status_code=201)
def create_scheme(body: SchemeCreate, db: Session = Depends(get_db)):
    s = Scheme(**body.model_dump())
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


@router.get("/{scheme_id}", response_model=SchemeOut)
def get_scheme(scheme_id: int, db: Session = Depends(get_db)):
    s = db.get(Scheme, scheme_id)
    if not s:
        raise HTTPException(404, "Scheme not found")
    return s


@router.put("/{scheme_id}", response_model=SchemeOut)
def update_scheme(scheme_id: int, body: SchemeUpdate, db: Session = Depends(get_db)):
    s = db.get(Scheme, scheme_id)
    if not s:
        raise HTTPException(404, "Scheme not found")
    for k, v in body.model_dump().items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s


@router.delete("/{scheme_id}", status_code=204)
def delete_scheme(scheme_id: int, db: Session = Depends(get_db)):
    s = db.get(Scheme, scheme_id)
    if not s:
        raise HTTPException(404, "Scheme not found")
    if s.is_builtin:
        raise HTTPException(400, "Cannot delete built-in scheme")
    db.delete(s)
    db.commit()


@router.post("/{scheme_id}/copy", response_model=SchemeOut, status_code=201)
def copy_scheme(scheme_id: int, db: Session = Depends(get_db)):
    s = db.get(Scheme, scheme_id)
    if not s:
        raise HTTPException(404, "Scheme not found")
    new_s = Scheme(
        name=f"{s.name} (副本)",
        description=s.description,
        is_builtin=False,
        match_mode=s.match_mode,
        min_match=s.min_match,
    )
    db.add(new_s)
    db.flush()
    for r in s.rules:
        db.add(Rule(
            scheme_id=new_s.id,
            sort_order=r.sort_order,
            template_id=r.template_id,
            name=r.name,
            category=r.category,
            data_source=r.data_source,
            metric=r.metric,
            operator=r.operator,
            value=r.value,
            lookback_days=r.lookback_days,
            params=r.params,
            enabled=r.enabled,
        ))
    db.commit()
    db.refresh(new_s)
    return new_s


# ---- Rules ----

@router.post("/{scheme_id}/rules", response_model=RuleOut, status_code=201)
def add_rule(scheme_id: int, body: RuleCreate, db: Session = Depends(get_db)):
    s = db.get(Scheme, scheme_id)
    if not s:
        raise HTTPException(404, "Scheme not found")
    r = Rule(scheme_id=scheme_id, **body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.put("/{scheme_id}/rules/reorder", response_model=list[RuleOut])
def reorder_rules(scheme_id: int, body: ReorderRequest, db: Session = Depends(get_db)):
    s = db.get(Scheme, scheme_id)
    if not s:
        raise HTTPException(404, "Scheme not found")
    rule_map = {r.id: r for r in s.rules}
    for idx, rid in enumerate(body.rule_ids):
        if rid in rule_map:
            rule_map[rid].sort_order = idx
    db.commit()
    db.refresh(s)
    return s.rules


@router.put("/{scheme_id}/rules/{rule_id}", response_model=RuleOut)
def update_rule(scheme_id: int, rule_id: int, body: RuleUpdate, db: Session = Depends(get_db)):
    r = db.get(Rule, rule_id)
    if not r or r.scheme_id != scheme_id:
        raise HTTPException(404, "Rule not found")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{scheme_id}/rules/{rule_id}", status_code=204)
def delete_rule(scheme_id: int, rule_id: int, db: Session = Depends(get_db)):
    r = db.get(Rule, rule_id)
    if not r or r.scheme_id != scheme_id:
        raise HTTPException(404, "Rule not found")
    db.delete(r)
    db.commit()
