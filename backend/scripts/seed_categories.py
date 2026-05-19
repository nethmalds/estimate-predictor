import sys
from pathlib import Path

# Ensure imports work when run directly
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from infrastructure.data_layer.database.session import SessionLocal
from infrastructure.data_layer.database.models.category import Category

CATEGORIES = [
    ("brick_masonry", "Brick Masonry", "All brick and block masonry works"),
    ("concrete_works", "Concrete Works", "In-situ and precast concrete works"),
    ("demolition_and_removal", "Demolition & Removal", "Demolishing and clearing away structures"),
    ("doors_windows_and_glazing", "Doors, Windows & Glazing", "Installation of doors, windows, and glass panels"),
    ("electrical_and_mechanical", "Electrical & Mechanical", "Electrical wiring, fixtures, and mechanical systems"),
    ("excavation_and_earthwork", "Excavation & Earthwork", "Site clearing, excavation, and earthworks"),
    ("external_and_civil_works", "External & Civil Works", "Paving, landscaping, and civil works outside the main building"),
    ("flooring_and_tiling", "Flooring & Tiling", "Floor finishes, screeding, and tiling works"),
    ("formwork", "Formwork", "Temporary moulds for concrete pouring"),
    ("miscellaneous", "Miscellaneous", "General or unclassified items"),
    ("other", "Other", "Other works not categorized"),
    ("painting_and_finishes", "Painting & Finishes", "Surface finishes, painting, and decoration"),
    ("piling_and_substructure", "Piling & Substructure", "Deep foundations and substructure works"),
    ("plastering_and_rendering", "Plastering & Rendering", "Wall plastering, skimming, and rendering"),
    ("preliminary_and_general", "Preliminary & General", "Site setup, securities, and preliminary project requirements"),
    ("reinforcement", "Reinforcement", "Steel rebar and mesh for concrete reinforcement"),
    ("roofing_and_ceiling", "Roofing & Ceiling", "Roof structures, covering, and ceiling finishes"),
    ("sanitary_and_plumbing", "Sanitary & Plumbing", "Water supply, drainage, and sanitary fixtures"),
    ("testing_and_commissioning", "Testing & Commissioning", "Testing systems and commissioning building operations"),
]

def seed_categories():
    db = SessionLocal()
    try:
        added_count = 0
        skipped_count = 0
        for code, name, desc in CATEGORIES:
            existing = db.query(Category).filter(Category.code == code).first()
            if not existing:
                category = Category(code=code, name=name, description=desc)
                db.add(category)
                added_count += 1
            else:
                skipped_count += 1
        db.commit()
        if added_count > 0:
            print(f"Successfully seeded {added_count} new categories.")
        if skipped_count > 0:
            print(f"Skipped {skipped_count} categories (already exist in database).")
    except Exception as e:
        db.rollback()
        print(f"Failed to seed categories: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed_categories()
