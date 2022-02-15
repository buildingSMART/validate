import sys, os
import ifcopenshell
from helper import database

ifc_fn = sys.argv[1]
ifc_file = ifcopenshell.open(ifc_fn)

try:
    detected_mvd = ifc_file.header.file_description.description[0].split(" ", 1)[1]
    detected_mvd = detected_mvd[1:-1]
except:
    detected_mvd = "no MVD detected"

try:
    authoring_app = ifc_file.by_type("IfcApplication")[0].ApplicationFullName
except:
    authoring_app = 'no authoring app detected'

with database.Session() as session:
    model = session.query(database.model).filter(database.model.code == ifc_fn[:-4]).all()[0]
    model.size = str(round(os.path.getsize(ifc_fn)*10**-6)) + "MB"
    model.schema = ifc_file.schema
    model.authoring_application = authoring_app
    model.mvd = detected_mvd
    model.number_of_elements = len(ifc_file.by_type("IfcBuildingElement"))
    model.number_of_geometries = len(ifc_file.by_type("IfcShapeRepresentation"))
    model.number_of_properties = len(ifc_file.by_type("IfcProperty"))

    session.commit()
    session.close()



