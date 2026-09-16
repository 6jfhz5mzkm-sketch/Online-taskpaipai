"""新手引导服务(对齐 backend tour.service:merchant.tour_seen 原生SQL)。"""
from sqlalchemy import text
from sqlalchemy.orm import Session


def get_seen(db: Session, merchant_id: str):
    row = db.execute(text("SELECT tour_seen FROM merchant WHERE merchant_id = :m"), {"m": merchant_id}).mappings().first()
    return {"seen": (int(row["tour_seen"] or 0) == 1) if row else False}


def mark_seen(db: Session, merchant_id: str):
    db.execute(text("UPDATE merchant SET tour_seen = 1 WHERE merchant_id = :m"), {"m": merchant_id})
    db.commit()
    return {"success": True}


def reset_seen(db: Session, merchant_id: str):
    db.execute(text("UPDATE merchant SET tour_seen = 0 WHERE merchant_id = :m"), {"m": merchant_id})
    db.commit()
    return {"success": True}
