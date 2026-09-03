#!/usr/bin/env python3
"""Idempotently seed 50 diverse demo users and 15 public campus activities."""

from __future__ import annotations

import random
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import SessionLocal  # noqa: E402
from backend.app.config import get_settings  # noqa: E402
from backend.app.models import Activity, User  # noqa: E402
from backend.app.security import hash_password  # noqa: E402


CAMPUSES = ["西区", "东区", "北区"]
GRADES = ["大一", "大二", "大三", "大四", "研一", "研二"]
MAJORS = ["计算机", "中文", "金融", "机械", "建筑", "生物", "新闻", "数学"]
INTERESTS = [
    "羽毛球",
    "跑步",
    "摄影",
    "阅读",
    "电影",
    "音乐",
    "桌游",
    "篮球",
    "编程",
    "英语",
]
TIMES = ["周六下午", "周日下午", "工作日晚上", "周末上午", "晚上"]
GOALS = ["运动搭子", "兴趣朋友", "学习搭子", "活动伙伴"]
STYLES = ["慢热", "随和", "外向", "安静"]
DEMO_PASSWORD = "CampusDemo123!"
USTC_DOMAIN = "ustc.edu.cn"


ACTIVITIES = [
    ("羽毛球约球", "西区", "西区体育馆", "周六下午", ["羽毛球", "休闲"]),
    ("校园夜跑", "西区", "西区操场", "工作日晚上", ["跑步"]),
    ("摄影 Walk", "东区", "东区银杏大道", "周日下午", ["摄影", "散步"]),
    ("考研自习", "北区", "图书馆 3F", "周末上午", ["学习", "考研"]),
    ("英语角", "东区", "国际交流中心", "周六下午", ["英语", "交流"]),
    ("桌游之夜", "西区", "学生活动中心", "周六晚上", ["桌游"]),
    ("三人篮球", "北区", "北区球场", "周日下午", ["篮球"]),
    ("青年读书会", "东区", "东区图书馆", "周日下午", ["阅读"]),
    ("Python 学习小组", "西区", "创新中心", "工作日晚上", ["编程", "学习"]),
    ("校园乐队开放排练", "北区", "大学生活动室", "周六下午", ["音乐"]),
    ("电影交流会", "东区", "报告厅", "周六晚上", ["电影"]),
    ("晨间瑜伽", "西区", "湖畔草坪", "周末上午", ["瑜伽", "运动"]),
    ("飞盘体验", "北区", "北区操场", "周六下午", ["飞盘", "运动"]),
    ("数学互助答疑", "东区", "理科楼", "工作日晚上", ["数学", "学习"]),
    ("校园志愿服务", "西区", "青年之家", "周日下午", ["志愿", "公益"]),
]


def upgrade_schema() -> None:
    """Bring the database to the migration head before standalone seeding."""

    if get_settings().data_backend == "cloudbase_http":
        # Shared CloudBase PG has no PostgreSQL protocol connection. Its schema
        # is initialized once from deployment/cloudbase_schema.sql in the console.
        return

    config = Config(str(ROOT / "alembic.ini"))
    command.upgrade(config, "head")


def make_users() -> list[User]:
    rng = random.Random(20250816)
    users = [
        User(
            id="user001",
            nickname="小宇",
            school_email=f"user001@{USTC_DOMAIN}",
            identity_provider="email",
            school="中国科学技术大学",
            campus="西区",
            grade="研一",
            major="计算机",
            bio="喜欢轻松运动和记录校园生活。",
            social_goals=["运动搭子", "兴趣朋友"],
            interests=["羽毛球", "跑步", "摄影"],
            activities=["羽毛球", "跑步", "摄影"],
            availability=["周末下午"],
            social_style="慢热",
            avoidances=["竞技强度过高"],
            is_mock=True,
        ),
        User(
            id="user002",
            nickname="小林",
            school_email=f"user002@{USTC_DOMAIN}",
            identity_provider="email",
            school="中国科学技术大学",
            campus="西区",
            grade="研一",
            major="新闻",
            bio="羽毛球休闲选手，也爱拍照。",
            social_goals=["运动搭子", "兴趣朋友"],
            interests=["羽毛球", "摄影", "电影"],
            activities=["羽毛球", "摄影"],
            availability=["周六下午", "工作日晚上"],
            social_style="随和",
            is_mock=True,
        ),
        User(
            id="user003",
            nickname="阿青",
            school_email=f"user003@{USTC_DOMAIN}",
            identity_provider="email",
            school="中国科学技术大学",
            campus="西区",
            grade="大三",
            major="建筑",
            bio="周末约球，水平休闲。",
            social_goals=["运动搭子"],
            interests=["羽毛球", "跑步"],
            activities=["羽毛球", "跑步"],
            availability=["周六下午"],
            social_style="慢热",
            is_mock=True,
        ),
        User(
            id="user004",
            nickname="可欣",
            school_email=f"user004@{USTC_DOMAIN}",
            identity_provider="email",
            school="中国科学技术大学",
            campus="东区",
            grade="研二",
            major="金融",
            bio="喜欢羽毛球和英语。",
            social_goals=["运动搭子", "活动伙伴"],
            interests=["羽毛球", "英语"],
            activities=["羽毛球", "英语角"],
            availability=["周六下午"],
            social_style="外向",
            is_mock=True,
        ),
    ]
    for number in range(5, 51):
        interests = rng.sample(INTERESTS, k=rng.randint(2, 4))
        users.append(
            User(
                id=f"user{number:03d}",
                nickname=f"同学{number:02d}",
                school_email=f"user{number:03d}@{USTC_DOMAIN}",
                identity_provider="email",
                school="中国科学技术大学",
                campus=rng.choice(CAMPUSES),
                grade=rng.choice(GRADES),
                major=rng.choice(MAJORS),
                bio=f"喜欢{'、'.join(interests[:2])}，想认识校园伙伴。",
                social_goals=rng.sample(GOALS, k=rng.randint(1, 2)),
                interests=interests,
                activities=interests[: rng.randint(1, len(interests))],
                availability=rng.sample(TIMES, k=rng.randint(1, 2)),
                social_style=rng.choice(STYLES),
                avoidances=[],
                recommendation_enabled=number % 19 != 0,
                is_mock=True,
            )
        )
    return users


def seed(db=None) -> tuple[int, int]:
    owns_session = db is None
    db = db or SessionLocal()
    try:
        user_count = 0
        demo_password_hash = hash_password(DEMO_PASSWORD)
        for user in make_users():
            user.verified = True
            user.campus_verified = True
            existing = db.get(User, user.id)
            if existing is None:
                user.password_hash = demo_password_hash
                db.add(user)
                user_count += 1
            else:
                existing.verified = True
                existing.campus_verified = True
                existing.school = user.school
                existing.is_mock = True
                if not existing.password_hash:
                    existing.password_hash = demo_password_hash
                if existing.school_email is None or existing.school_email.endswith(
                    "@example.edu"
                ):
                    existing.school_email = user.school_email
                if not existing.identity_provider:
                    existing.identity_provider = user.identity_provider
        activity_count = 0
        for index, (name, campus, location, time, tags) in enumerate(ACTIVITIES, 1):
            activity_id = f"activity{index:03d}"
            if db.get(Activity, activity_id) is None:
                db.add(
                    Activity(
                        id=activity_id,
                        name=name,
                        campus=campus,
                        location=location,
                        time=time,
                        tags=tags,
                        capacity=20,
                        public=True,
                    )
                )
                activity_count += 1
        db.commit()
        return user_count, activity_count
    finally:
        if owns_session:
            db.close()


if __name__ == "__main__":
    upgrade_schema()
    users, activities = seed()
    print(f"Seed complete: added {users} users and {activities} activities.")
