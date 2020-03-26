from sqlalchemy.orm import sessionmaker
import sqlalchemy
import sys

sys.path.append('../')
from ORM.tables import Chore, Person, Assignment
import random

print("SQLAlchemy Version: {}".format(sqlalchemy.__version__))  # Mostly for debug if necessary

engine = sqlalchemy.create_engine(open("../resources/mysqlEngine.txt", "r").readline(), pool_recycle=3600, echo=False)

session_maker = sessionmaker(bind=engine)

session = session_maker()

for _ in range(100):
    a: Assignment = sqlalchemy.orm.aliased(Assignment)  # Alias Assignment table to 'a'

    chore_assignment_unique = session.query(Chore, a).join(a, isouter=True).filter(
        a.id == 40
        #        or_(
        #            a.id == session.query(func.max(Assignment.id)).filter(
        #                Assignment.chore_id == a.chore_id
        #            ),
        #            a.id.is_(None)
        #        )
    )

    for row in chore_assignment_unique:
        chore: Chore = row[0]
        assignment: Assignment = row[1]
        next_person: Person = Person()

        # check for chore frequency last chore completion to be long enough ago that it's past the freq.
        if assignment is not None:
            # assignment.completionDate is not None and \
            # assignment.completionDate <= (datetime.utcnow() - timedelta(days=chore.frequency)):
            #     Recorded completion  before or on       now   - (frequency) days
            if chore.id == 1:
                print("Prior assignment found for ", assignment.chore.choreName)
            persons = []
            # create a list of people who can do this chore.
            for p in chore.validPersons:
                persons.append(p.id)

            if len(persons) == 1:
                next_person = session.query(Person).filter(Person.id.in_(persons)).all()
                next_person = next_person[random.randint(0, len(next_person) - 1)]

            else:
                # choose the next person to do the chore. Make sure to exclude last person who did it.
                '''
                select * from person p where
                    p.id in (\\external list of valid persons\\) 
                    and
                    p.id != \\prior assignment\\.person.id
                '''
                next_person = session.query(Person).filter(
                    Person.id.in_(persons),
                    Person.id != assignment.completedBy_id
                ).all()
                if chore.id == 1:
                    print("Possible choices:", [i.id for i in next_person])
                next_person = next_person[random.randint(0, len(next_person) - 1)]

            if chore.id == 1:
                print("Last completed by: ", assignment.completedBy_id)
                print(chore.choreName, "is next done by person with id", next_person.id)
        elif assignment is None:
            if chore.id == 1:
                print("New assignment for", chore.choreName)
            # in this case, create a list of all people who can do this chore
            persons = []
            for p in chore.validPersons:
                persons.append(p.id)
            # choose who will do this chore next
            next_person = session.query(Person).filter(Person.id.in_(persons)).all()
            next_person = next_person[random.randint(0, len(next_person) - 1)]
            if chore.id == 1:
                print(chore.choreName, "is next done by person with id", next_person.id)

        # if there is no next person, pass this loop
        if next_person.name is None:
            continue
