git submodule foreach --recursive git rev-parse HEAD
echo "Remote origin for 'ifc_gherkin_rules'"
cd ./backend/apps/ifc_validation/checks/ifc_gherkin_rules && git remote get-url origin
echo "HEAD of 'ifc_gherkin_rules"
git rev-parse --short HEAD
echo "HEAD of 'validate'" 
cd ../../../..
git rev-parse --short HEAD
