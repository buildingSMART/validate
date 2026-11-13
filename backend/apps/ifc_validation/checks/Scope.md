### Syntax

 - File is a 10303-21 file
 - File has header
 - File has valid overall syntax
 - File has valid string encoding
 - File has no duplicate ids
 - File has no 0 ids (todo)
 
### IFC101

 - schema is actual

### Schema

 - attribute types
 - aggregate lengths
 - inverses
 - where rules and functions

### Header validation

 - header conforms to policy
 
### 000-rules
 
 - **availability**
   
   *"Certain patterns of information exchange are present in a model"*
   
   (e.g GridPlacement is used somewhere)

### Normative rules

 - **validity**
   
   *"Exchange follows expected structure and data types in addition to constraints in the schema"*

   (e.g Alignment <-Nests-> Horizontal)

 - **correctness**
   
   *"No contradictions of universal constraints"*

   (e.g No duplicate points in polyloop; planar face is planar)

 - **logical consistency** (end-goal of software cert)

   *"No contradictions of 'direct' statements within exchange"*
 
   (e.g same number of segments for alignment domain logic and representation)
 
 - **reliability** (end-goal of validation service)

   *"Arbitrary fragments of data can be relied upon"*

   (e.g properties agree with geometry; multiple representations for same element are in agreement; an element classified as a "wall" also behaves like a "wall")

 - **completeness** (100% out of scope, more or less intractable)
   
   *"Data is complete"*


### Best practices

 - **usefulness**