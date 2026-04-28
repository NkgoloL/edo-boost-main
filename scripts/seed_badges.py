import asyncio
import uuid
from sqlalchemy import text
from app.api.core.database import AsyncSessionFactory

async def seed_badges():
    async with AsyncSessionFactory() as session:
        print("Seeding badges...")
        
        badges = [
            # Streak Badges
            {"key": "streak_3", "name": "Streak Starter", "desc": "Active for 3 days!", "type": "streak", "thresh": 3, "band": "all"},
            {"key": "streak_7", "name": "Weekly Warrior", "desc": "Active for 7 days!", "type": "streak", "thresh": 7, "band": "all"},
            {"key": "streak_30", "name": "Monthly Legend", "desc": "Active for 30 days!", "type": "streak", "thresh": 30, "band": "all"},
            
            # Mastery Badges
            {"key": "mastery_math", "name": "Math Whiz", "desc": "Reached 80% Math mastery", "type": "mastery", "thresh": 0.8, "band": "all"},
            {"key": "mastery_eng", "name": "Word Smith", "desc": "Reached 80% English mastery", "type": "mastery", "thresh": 0.8, "band": "all"},
            
            # XP / Milestone Badges
            {"key": "xp_1000", "name": "Kilobit", "desc": "Earned 1,000 total XP", "type": "milestone", "thresh": 1000, "band": "all"},
            {"key": "xp_5000", "name": "Power User", "desc": "Earned 5,000 total XP", "type": "milestone", "thresh": 5000, "band": "all"},
        ]
        
        for b in badges:
            await session.execute(
                text("""
                    INSERT INTO badges 
                    (badge_id, badge_key, name, description, badge_type, threshold, icon_url, grade_band, is_active)
                    VALUES (:id, :key, :name, :desc, :type, :thresh, :icon, :band, TRUE)
                    ON CONFLICT (badge_key) DO UPDATE SET
                        name = EXCLUDED.name,
                        description = EXCLUDED.description,
                        threshold = EXCLUDED.threshold
                """),
                {
                    "id": str(uuid.uuid4()),
                    "key": b["key"],
                    "name": b["name"],
                    "desc": b["desc"],
                    "type": b["type"],
                    "thresh": b["thresh"],
                    "icon": f"/badges/{b['key']}.png",
                    "band": b["band"]
                }
            )
        
        await session.commit()
        print(f"Successfully seeded {len(badges)} badges.")

if __name__ == "__main__":
    asyncio.run(seed_badges())
