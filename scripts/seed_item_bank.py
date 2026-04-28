import asyncio
import random
import uuid
import json
from sqlalchemy import text
from app.api.core.database import AsyncSessionFactory
from app.api.ml.irt_engine import SubjectCode

# Subject templates
TEMPLATES = {
    SubjectCode.MATH: [
        {"q": "What is {a} + {b}?", "ans": "{res}", "opts": ["{res}", "{w1}", "{w2}", "{w3}"], "concept": "ADD"},
        {"q": "What is {a} - {b}?", "ans": "{res}", "opts": ["{res}", "{w1}", "{w2}", "{w3}"], "concept": "SUB"},
        {"q": "What is {a} × {b}?", "ans": "{res}", "opts": ["{res}", "{w1}", "{w2}", "{w3}"], "concept": "MULT"},
        {"q": "Sipho has {a} apples and gives {b} to his friend. How many left?", "ans": "{res}", "opts": ["{res}", "{w1}", "{w2}", "{w3}"], "concept": "WORD_PROB"},
    ],
    SubjectCode.ENG: [
        {"q": "Choose the correct spelling for '{word}':", "ans": "{word}", "opts": ["{word}", "{w1}", "{w2}", "{w3}"], "concept": "SPELL"},
        {"q": "What is the opposite of '{word}'?", "ans": "{res}", "opts": ["{res}", "{w1}", "{w2}", "{w3}"], "concept": "OPPOSITE"},
        {"q": "In the sentence 'The {animal} {verb} quickly', what is the verb?", "ans": "{verb}", "opts": ["{verb}", "{n1}", "{n2}", "{n3}"], "concept": "GRAMMAR"},
    ],
}

async def seed():
    async with AsyncSessionFactory() as session:
        print("Seeding item bank...")
        
        items = []
        
        # Math items (Grades 1-7)
        for grade in range(1, 8):
            for i in range(5): # 5 math items per grade
                a = random.randint(1, 10 * grade)
                b = random.randint(1, 10 * grade)
                res = a + b
                items.append({
                    "item_id": f"MATH_ADD_G{grade}_{i}",
                    "subject": "MATH",
                    "grade": grade,
                    "concept": "MATH_ADD",
                    "diff": (grade - 3) / 2.0 + (i - 2) * 0.2,
                    "disc": 1.2 + random.random() * 0.4,
                    "q": f"What is {a} + {b}?",
                    "opts": [str(res), str(res+1), str(res-1), str(res+10)],
                    "ans": str(res)
                })

        # English items (Grades 1-7)
        words = ["elephant", "giraffe", "zebra", "lion", "leopard", "rhino", "buffalo"]
        for grade in range(1, 8):
            for i in range(5):
                word = random.choice(words)
                items.append({
                    "item_id": f"ENG_SPELL_G{grade}_{i}",
                    "subject": "ENG",
                    "grade": grade,
                    "concept": "ENG_SPELL",
                    "diff": (grade - 3) / 2.0 + (i - 2) * 0.2,
                    "disc": 1.1 + random.random() * 0.5,
                    "q": f"Which is the correct spelling for the animal?",
                    "opts": [word, word.replace("ph", "f"), word.replace("e", "i"), "elefant"],
                    "ans": word
                })

        # Life Orientation / Science / Social Science (Mix)
        other_subjects = ["NS", "SS", "LIFE"]
        for sub in other_subjects:
            for grade in range(1, 8):
                for i in range(3):
                    items.append({
                        "item_id": f"{sub}_G{grade}_{i}",
                        "subject": sub,
                        "grade": grade,
                        "concept": f"{sub}_GEN",
                        "diff": (grade - 3) / 2.0,
                        "disc": 1.0,
                        "q": f"Sample question for {sub} Grade {grade} No {i}",
                        "opts": ["Correct", "Wrong 1", "Wrong 2", "Wrong 3"],
                        "ans": "Correct"
                    })

        # Insert items
        for item in items:
            await session.execute(
                text("""
                    INSERT INTO item_bank 
                    (item_id, subject_code, grade_level, concept_code, difficulty, discrimination, 
                     guessing, content, options, correct_answer, is_active, version)
                    VALUES (:id, :sub, :grade, :concept, :diff, :disc, 0.25, :content, :opts, :ans, TRUE, 1)
                    ON CONFLICT (item_id) DO UPDATE SET
                        content = EXCLUDED.content,
                        options = EXCLUDED.options,
                        correct_answer = EXCLUDED.correct_answer
                """),
                {
                    "id": item["item_id"],
                    "sub": item["subject"],
                    "grade": item["grade"],
                    "concept": item["concept"],
                    "diff": item["diff"],
                    "disc": item["disc"],
                    "content": item["q"],
                    "opts": json.dumps(item["opts"]),
                    "ans": item["ans"]
                }
            )
        
        await session.commit()
        print(f"Successfully seeded {len(items)} items.")

if __name__ == "__main__":
    asyncio.run(seed())
