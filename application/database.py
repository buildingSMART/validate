##################################################################################
#                                                                                #
# Copyright (c) 2020 AECgeeks                                                    #
#                                                                                #
# Permission is hereby granted, free of charge, to any person obtaining a copy   #
# of this software and associated documentation files (the "Software"), to deal  #
# in the Software without restriction, including without limitation the rights   #
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell      #
# copies of the Software, and to permit persons to whom the Software is          #
# furnished to do so, subject to the following conditions:                       #
#                                                                                #
# The above copyright notice and this permission notice shall be included in all #
# copies or substantial portions of the Software.                                #
#                                                                                #
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR     #
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,       #
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE    #
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER         #
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,  #
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE  #
# SOFTWARE.                                                                      #
#                                                                                #
##################################################################################

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from sqlalchemy.inspection import inspect
from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Enum
from sqlalchemy_utils import database_exists, create_database
from sqlalchemy.orm import relationship
import os
import datetime

DEVELOPMENT = os.environ.get('environment', 'production').lower() == 'development'

if DEVELOPMENT:
    file_path = os.path.join(os.path.dirname(__file__), "ifc-pipeline.db") 
    engine = create_engine(f'sqlite:///{file_path}', connect_args={'check_same_thread': False})
else:
    host = os.environ.get('POSTGRES_HOST', 'localhost')
    password = os.environ['POSTGRES_PASSWORD']
    engine = create_engine(f"postgresql://postgres:{password}@{host}:5432/bimsurfer2")
  
Session = sessionmaker(bind=engine)

Base = declarative_base()

class Serializable(object):
    def serialize(self):
        # Transforms data from dataclasses to a dict,
        # storing primary key of references and handling date format
        d = {}
        for attribute in inspect(self).attrs.keys():
            if isinstance(getattr(self, attribute), (list, tuple)):
                d[attribute] = [element.id for element in getattr(self, attribute)]
            elif isinstance(getattr(self, attribute), datetime.datetime):
                d[attribute] = getattr(self, attribute).strftime("%Y-%m-%d %H:%M:%S")
            else:
                d[attribute] = getattr(self, attribute)
        return d


class user(Base, Serializable):
    __tablename__ = 'users'

    id = Column(String, primary_key=True)
    email = Column(String)
    family_name = Column(String)
    given_name = Column(String)
    name = Column(String)
    models = relationship("model") 

    def __init__(self, id, email, family_name, given_name, name):
        self.id = id
        self.email = email
        self.family_name = family_name
        self.given_name = given_name
        self.name = name
        

class model(Base, Serializable):
    __tablename__ = 'models'

    id = Column(Integer, primary_key=True)
    code = Column(String)
    filename = Column(String)
    user_id = Column(String, ForeignKey('users.id'))

    progress = Column(Integer, default=-1)
    date = Column(DateTime, server_default=func.now())

    license = Column(Enum('private','CC','MIT','GPL','LGPL'), server_default="private")
    hours = Column(Float)
    details = Column(String)

    number_of_elements = Column(Integer)
    number_of_geometries = Column(Integer)
    number_of_properties = Column(Integer)
    
    authoring_application = Column(String)
    schema = Column(String)
    size = Column(String)
    mvd = Column(String)

    status_syntax = Column(Enum('n','v','w','i'), default='n')
    status_schema = Column(Enum('n','v','w','i'), default='n')
    status_bsdd = Column(Enum('n','v','w','i'), default='n')
    status_mvd = Column(Enum('n','v','w','i'), default='n')
    status_ids= Column(Enum('n','v','w','i'), default='n')
    
    instances = relationship("ifc_instance")

    def __init__(self, code, filename, user_id):
        self.code = code
        self.filename = filename
        self.user_id = user_id


class file(Base, Serializable):
    __tablename__ = 'files'

    id = Column(Integer, primary_key=True)
    code = Column(String)
    filename = Column(String)
 
    def __init__(self, code, filename):
        self.code = code
        self.filename = filename


class bsdd_validation_task(Base, Serializable):
    __tablename__ = 'bSDD_validation_tasks'

    id = Column(Integer, primary_key=True)
    validated_file = Column(Integer, ForeignKey('models.id'))
    validation_start_time = Column(DateTime)
    validation_end_time = Column(DateTime)

    results = relationship("bsdd_result")

    def __init__(self, validated_file):
        self.validated_file = validated_file
        

class ifc_instance(Base, Serializable):
    __tablename__ = 'instances'

    id = Column(Integer, primary_key=True)
    global_id = Column(String)
    file = Column(Integer, ForeignKey('models.id'))
    ifc_type = Column(String)
    bsdd_results = relationship("bsdd_result")
    
    def __init__(self, global_id, ifc_type, file):
        self.global_id = global_id
        self.ifc_type = ifc_type
        self.file = file

     
class bsdd_result(Base, Serializable):
    __tablename__ = 'bSDD_results'

    id = Column(Integer, primary_key=True)
    task_id = Column(Integer, ForeignKey('bSDD_validation_tasks.id'))
    instance_id = Column(Integer, ForeignKey('instances.id'))
    bsdd_classification_uri = Column(String)
    bsdd_property_uri = Column(String)
    bsdd_property_constraint = Column(String)
    bsdd_type_constraint = Column(String)
    ifc_property_set = Column(String)
    ifc_property_name = Column(String)
    ifc_property_type = Column(String)
    ifc_property_value = Column(String)

    
    def __init__(self, task_id):
        self.task_id = task_id
     
def initialize():
    if not database_exists(engine.url):
        create_database(engine.url)
    Base.metadata.create_all(engine)


if __name__ == "__main__" or DEVELOPMENT:
    initialize()
