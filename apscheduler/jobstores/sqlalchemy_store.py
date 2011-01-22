"""
Stores jobs in a database table using SQLAlchemy.
"""
import pickle

from apscheduler.jobstores.base import JobStore
from apscheduler.job import Job
from apscheduler.util import obj_to_ref

try:
    from sqlalchemy import *
except ImportError:
    raise ImportError('SQLAlchemyJobStore requires SQLAlchemy installed')


class SQLAlchemyJobStore(JobStore):
    def __init__(self, url=None, engine=None, tablename='apscheduler_jobs',
                 metadata=None, pickle_protocol=pickle.HIGHEST_PROTOCOL):
        self.jobs = []
        self.pickle_protocol = pickle_protocol

        if engine:
            self.engine = engine
        elif url:
            self.engine = create_engine(url)
        else:
            raise ValueError('Need either "engine" or "url" defined')

        self.jobs_t = Table(tablename, metadata or MetaData(),
            Column('id', Integer, primary_key=True),
            Column('trigger', PickleType(pickle_protocol, mutable=False),
                   nullable=False),
            Column('func_ref', String(1024), nullable=False),
            Column('args', PickleType(pickle_protocol, mutable=False),
                   nullable=False),
            Column('kwargs', PickleType(pickle_protocol, mutable=False),
                   nullable=False),
            Column('name', Unicode(1024), unique=True),
            Column('misfire_grace_time', Integer, nullable=False),
            Column('max_runs', Integer),
            Column('max_concurrency', Integer),
            Column('next_run_time', DateTime, nullable=False),
            Column('runs', BigInteger))

        self.jobs_t.create(self.engine, True)

    def add_job(self, job):
        job.func_ref = obj_to_ref(job.func)
        job_dict = job.__getstate__()
        result = self.engine.execute(self.jobs_t.insert().values(**job_dict))
        job.id = result.inserted_primary_key[0]
        self.jobs.append(job)

    def remove_job(self, job):
        delete = self.jobs_t.delete().where(self.jobs_t.c.id == job.id)
        self.engine.execute(delete)
        self.jobs.remove(job)

    def load_jobs(self):
        jobs = []
        for row in self.engine.execute(select([self.jobs_t])):
            job = Job.__new__(Job)
            job_dict = dict(row.items())
            job.__setstate__(job_dict)
            jobs.append(job)
        self.jobs = jobs

    def update_job(self, job):
        job_dict = job.__getstate__()
        update = self.jobs_t.update().where(self.jobs_t.c.id == job.id).\
            values(next_run_time=job_dict['next_run_time'],
                   runs=job_dict['runs'])
        self.engine.execute(update)

    def __repr__(self):
        return '<%s (url=%s)>' % (self.__class__.__name__, self.engine.url)