'''
sipShell2Abq2D.py: procedure part of the 2DImage2Mesh project
Create a 2d quadrangular mesh from an image using scanIP (Simpleware Ltd) and Abaqus (Dassault Systeme)
----------------------------------------------
INSTRUCTIONS: see readme.md or 2DIm2Mesh.txt
----------------------------------------------
Author: MMENGONI, Jan 2014
----------------------------------------------
'''

## default abaqus modules
from abaqus import *
backwardCompatibility.setValues(reportDeprecated=False)
import mesh

#-----------------------------------------------------
def shellTo2DGeo(myModel,seedSize=0.5):
    from abaqusConstants import TWO_D_PLANAR,DEFORMABLE_BODY,OFF,ON,QUAD,CPS3,CPS4R,STANDARD,ENHANCED

    ## ELEMENT INTEGRATION (2D elements: CPE=plane strain, CPS=plane stress)
    elemType1 = mesh.ElemType(elemCode=CPS4R, elemLibrary=STANDARD, hourglassControl=ENHANCED)
    elemType2 = mesh.ElemType(elemCode=CPS3, elemLibrary=STANDARD)
    
    myAssembly = myModel.rootAssembly
    for myPart in myModel.parts.values():
        ## clean node list (remove nodes not in the zMin plane)
        #1/ find zMin...
        zCoord = list()
        nodeLabels = list()
        for node in myPart.nodes:
            zCoord.append(node.coordinates[2])
            nodeLabels.append(node.label)
        minZ = min(zCoord)
        #2/ build a list of nodes not in zMin
        remNodes = [nodeLabels[i] for i, x in enumerate(zCoord) if x > minZ+1e-10]
        #3/ remove those nodes
        if len(remNodes):
            myPart.SetFromNodeLabels(nodeLabels=remNodes, name='remNodeSet')
            myPart.deleteNode(nodes=myPart.sets['remNodeSet'], deleteUnreferencedNodes=ON)
            del myPart.sets['remNodeSet']
        del nodeLabels
        
        ## delete shell section assignments
        for sa,secAss in enumerate(myPart.sectionAssignments):
            del myPart.sectionAssignments[sa]
    
    myAssembly.regenerate()#needed to still have acces to assembly node sets
        
    ## for each set that make a shell, create a new part (by getting the external edges as Lines) and mesh it
    for myInstance in myAssembly.instances.values():
        for myISet in myInstance.sets.keys():
            if myISet.endswith('WITH_ZMIN'):
                mySketch = myModel.ConstrainedSketch(name='mySketch', sheetSize=30.0)
                for ele in myInstance.sets[myISet].elements:
                    for edge in ele.getElemEdges():
                        if len(edge.getElements())==1:
                            node = edge.getNodes()
                            pt1 = (node[0].coordinates[0],node[0].coordinates[1])
                            pt2 = (node[1].coordinates[0],node[1].coordinates[1])
                            mySketch.Line(point1=pt1,point2=pt2)
                myNewPart = myModel.Part(name=myISet.split('_')[1]+'_Geo', dimensionality=TWO_D_PLANAR, type=DEFORMABLE_BODY)
                myNewPart.BaseShell(sketch=mySketch)
                myNewPart.setMeshControls(regions=(myNewPart.faces[0],), elemShape=QUAD)
                myNewPart.seedPart(size=seedSize)#, deviationFactor=0.1, minSizeFactor=0.1)
                myNewPart.generateMesh()
                myNewPart.setElementType(regions=(myNewPart.faces[0],), elemTypes=(elemType1, elemType2))
                del mySketch
    # rebuild assembly sets as part sets and surfaces
    for setName in myAssembly.sets.keys():
        partName = setName.split('_')[1]+'_Geo'
        if myModel.parts.has_key(partName):
            part = myModel.parts[partName]
            #build a list of the assembly set node coord
            nodeCoord = tuple(node.coordinates for node in myAssembly.sets[setName].nodes)
            #find the part edges at those coord
            myEdgeList = list(part.edges.findAt((nC,)) for nC in nodeCoord)
            #for what ever reason when parts.edges[0] should be in the list it is not...
            #so here is a long way to add it if needed...
            #1/ build a list of all vertices in the edge list
            listVertices = list()
            for edge in myEdgeList:
                #myEdgeList is a list of edge entities, the edge itself is the first element of that entity --> edge[0]
                listVertices.extend([v for v in edge[0].getVertices() if v not in listVertices])
            #2/ parts.edges[0] has vertices (0,1) --> if those two vertices are in the list of all vertices, add part.edges[0] to myEdgeList
            if all(x in listVertices for x in [0,1]):
                pt0 = part.edges[0].getNodes()[0].coordinates
                pt1 = part.edges[0].getNodes()[1].coordinates
                newPt = ((pt0[0]+pt1[0])/2.,(pt0[1]+pt1[1])/2.,(pt0[2]+pt1[2])/2.)
                myEdgeList.append(part.edges.findAt((newPt,)))        
            #create set and surface
            part.Set(edges=myEdgeList,name=setName)
            part.Surface(side1Edges=myEdgeList,name=setName)
        del myAssembly.sets[setName]

    # delete old part,instance,sections,...
    del myAssembly.features['PART-1-1']
    del myModel.parts['PART-1']
    for sName in myModel.sections.keys():
       del myModel.sections[sName]
    
    ## add new parts to assembly - only after the initial instance has been deleted has they are not of the same type
    for part in myModel.parts.values():
       createInstanceAndAddtoAssembly(part,myAssembly,independent=False)
#-----------------------------------------------------
def createInstanceAndAddtoAssembly(part,assembly,independent=True):
    from abaqusConstants import OFF,ON
    myInstaneName = part.name.split('_')[0]+'_instance'
    if independent:
        myInstance = assembly.Instance(myInstaneName, part, dependent=OFF)
    else:
        myInstance = assembly.Instance(myInstaneName, part, dependent=ON)
    return myInstance