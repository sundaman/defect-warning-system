from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class Test(Base):
    __tablename__ = 'test'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    other = Column(String)

col1 = Test.name
col2 = Test.name
col3 = Test.other

print(f"Comparing distinct columns (name != other):")
try:
    if col1 != col3:
        print("Result: True (in if)")
    else:
        print("Result: False (in if)")
except Exception as e:
    print(f"Result: ERROR - {e}")

print(f"\nComparing same columns (name != name):")
try:
    if col1 != col2:
        print("Result: True")
    else:
        print("Result: False")
except Exception as e:
    print(f"Result: ERROR - {e}")

print(f"\nIdentity check (name is not other): {col1 is not col3}")
