import time

from sqlalchemy.orm import sessionmaker
import sqlalchemy
from ORM.tables import Chore, Person, Assignment
from sqlalchemy.sql.functions import func
from sqlalchemy.sql.expression import or_
import random

print("SQLAlchemy Version: {}".format(sqlalchemy.__version__))  # Mostly for debug if necessary

engine = sqlalchemy.create_engine(open("../resources/mysqlEngine.txt", "r").readline(), pool_recycle=3600, echo=False)

session_maker = sessionmaker(bind=engine)

session = session_maker()

while True:
    a: Assignment = sqlalchemy.orm.aliased(Assignment)  # Alias Assignment table to 'a'

    chore_assignment_unique = session.query(Chore, a).join(a, isouter=True).filter(
        or_(
            a.id == session.query(func.max(Assignment.id)).filter(
                Assignment.chore_id == a.chore_id
            ),
            a.id.is_(None)
        )
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
                next_person = next_person[random.randint(0, len(next_person) - 1)]
        elif assignment is None:
            # in this case, create a list of all people who can do this chore
            persons = []
            for p in chore.validPersons:
                persons.append(p.id)
            # choose who will do this chore next
            next_person = session.query(Person).filter(Person.id.in_(persons)).all()
            next_person = next_person[random.randint(0, len(next_person) - 1)]

        # if there is no next person, pass this loop
        if next_person.name is None:
            continue

        print(next_person.name)
    time.sleep(3)
