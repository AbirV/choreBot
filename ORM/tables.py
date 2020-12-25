from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import *
from datetime import datetime
import sys


Base = declarative_base()
meta: MetaData = Base.metadata
meta.schema = 'helper'

testing = False
for arg in sys.argv:
    if arg == 'testing':
        testing = True
        print("Loading test helper schema")
        meta.schema = 'helpertest'

people_chore_association = Table('peoplechoreassociation', meta,
                                 Column('chore_id', Integer, ForeignKey('chores.id')),
                                 Column('person_id', Integer, ForeignKey('person.id'))
                                 )


class Chore(Base):
    __tablename__ = 'chores'
    id = Column(Integer, primary_key=True)
    choreName = Column(String(length=50))
    desc = Column(String(length=150))
    validPersons = relationship("Person", secondary=people_chore_association)
    frequency = Column(Integer)
    channel = Column(String(length=18))


class Person(Base):
    __tablename__ = 'person'
    id = Column(Integer, primary_key=True)
    name = Column(String(length=30), unique=True)


class Assignment(Base):
    __tablename__ = 'assignments'
    id = Column(Integer, primary_key=True)
    chore_id = Column(Integer, ForeignKey('chores.id'))
    chore = relationship("Chore")
    person_id = Column(Integer, ForeignKey('person.id'))
    person = relationship("Person", foreign_keys=[person_id])

    assignmentDate = Column(DateTime, default=datetime.utcnow())
    completionDate = Column(DateTime)
    completedBy_id = Column(Integer, ForeignKey('person.id'))
    completedBy = relationship("Person", foreign_keys=[completedBy_id])
    lastReminder = Column(DateTime, default=datetime.utcnow())
