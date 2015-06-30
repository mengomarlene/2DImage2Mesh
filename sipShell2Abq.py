'''
sipShell2Abq.py: procedure part of the 2DImage2Mesh project
Create a 2D quadrangular mesh or a 3D hexahedral mesh (extrusion mesh) from one image using scanIP (Simpleware Ltd) and Abaqus (Dassault Systeme)
----------------------------------------------
INSTRUCTIONS: see readme.md or 2DIm2Mesh.txt
----------------------------------------------
Author: MMENGONI, Jun 2015
----------------------------------------------
v 0.2 (06/2015): add 3D mesh by extrusion, no set/surfaces reconstruction
v 0.1 (01/2014): first release, 2D quad mesh
'''

## default abaqus modules
from abaqus import *
backwardCompatibility.setValues(reportDeprecated=False)
import mesh

#-----------------------------------------------------
def clearUnwantedNodes(model):
    ## FOR EACH PART: CLEAR UNWANTED NODES AND DELETE SHELL SECTIONS
    for myPart in model.parts.values():
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
        #3/ remove those nodes (they have to be part of a set to do so, thus first create set - then delete nodes from set - then delete set)
        if len(remNodes):
            nodesSetToBeRem = myPart.SetFromNodeLabels(nodeLabels=remNodes, name='remNodeSet')
            myPart.deleteNode(nodes=nodesSetToBeRem, deleteUnreferencedNodes=ON)
            del nodesSetToBeRem
        del nodeLabels#that list is not needed any more!
        
        ## delete shell section assignments
        for sa in myPart.sectionAssignments: del sa
#-----------------------------------------------------
def createSketch(model,set):
    mySketch = model.ConstrainedSketch(name='mySketch', sheetSize=30.0)
    # loop over elements of the set and their edges
    for ele in set.elements:
        for edge in ele.getElemEdges():
            # if one edge belongs to only one element it means it is an edge or a contact edge, those are the target to build the geometry
            if len(edge.getElements())==1:
                # reads nodes coordinates of target elements
                node = edge.getNodes()
                pt1 = (node[0].coordinates[0],node[0].coordinates[1])
                pt2 = (node[1].coordinates[0],node[1].coordinates[1])
                # create geometrical line between those nodes
                mySketch.Line(point1=pt1,point2=pt2)
    return mySketch
#-----------------------------------------------------
def addPartsToAssembly(model):
    ## add new parts to assembly - only after the initial instance has been deleted has they are not of the same type
    for part in model.parts.values():
       myInstaneName = part.name.split('_')[0]+'_instance'
       myAssembly.Instance(myInstaneName, part, dependent=ON)
#-----------------------------------------------------
def deleteOldFeatures(model):
    from abaqusConstants import ON
    # delete old part,instance,sections,...
    del model.rootAssembly.features['PART-1-1']
    del model.parts['PART-1']
    for sName in model.sections.keys():
       del model.sections[sName]
#-----------------------------------------------------
#-----------------------------------------------------
def shellTo2DGeo(myModel,seedSize=0.5,elementType='CPS'):
    '''
    shellTo2DGeo is the function to be called from abaqus cae
    mandatory arguments:
     myModel: an abaqus model (model produced with scanIP and imported in abaqus)
    optional arguments:
     seedSize: the relative size of the new mesh points (0.5 means there will be two seeds per geometrical line ie one new element edge per old element edge at the boundaries)
     elementType: choose type of 2d element, anything else than 'CPS' will produce a plane strain mesh, default keeps plane stress
    '''
    ## load needed abaqus constants
    from abaqusConstants import TWO_D_PLANAR,DEFORMABLE_BODY,ON,QUAD,CPS3,CPS4R,CPE3,CPE4R,STANDARD,ENHANCED

    ## ELEMENT INTEGRATION (2D elements: CPE=plane strain, CPS=plane stress)
    # defines abaqus elements - hourglass controlled standard quadrangles (abaqus asks for the definition of the triangular elements even if they a not used!!)
    if elementType=:'CPS':
        elemType1 = mesh.ElemType(elemCode=CPS4R, elemLibrary=STANDARD, hourglassControl=ENHANCED)
        elemType2 = mesh.ElemType(elemCode=CPS3, elemLibrary=STANDARD)
    else:
        elemType1 = mesh.ElemType(elemCode=CPE4R, elemLibrary=STANDARD, hourglassControl=ENHANCED)
        elemType2 = mesh.ElemType(elemCode=CPE3, elemLibrary=STANDARD)
    
    myAssembly = myModel.rootAssembly
    clearUnwantedNodes(myModel)
    myAssembly.regenerate()#needed to still have access to assembly node sets
        
    ## for each set that makes a shell, create a new part (by getting the external edges as Lines) and mesh it
    # those sets are assembly sets defined by scanIP --> loop over assembly instances and over sets in those instances
    for myInstance in myAssembly.instances.values():
        for myISet in myInstance.sets.keys():
            # find set which is a shell (each set will form a new part)
            if myISet.endswith('WITH_ZMIN'):
                # create a new sketch to create a new geometrical part
                mySketch = createSketch(myModel,myInstance.sets[myISet])
                # create new part whose name will be 'nameOfTheCorrespondingScanIPMask_Geo'
                myNewPart = myModel.Part(name=myISet.split('_')[1]+'_Geo', dimensionality=TWO_D_PLANAR, type=DEFORMABLE_BODY)
                myNewPart.BaseShell(sketch=mySketch)
                # assign mesh controls and seeds
                myNewPart.setMeshControls(regions=(myNewPart.faces[0],), elemShape=QUAD)
                myNewPart.seedPart(size=seedSize)#, deviationFactor=0.1, minSizeFactor=0.1)
                # create new mesh
                myNewPart.generateMesh()
                myNewPart.setElementType(regions=(myNewPart.faces[0],), elemTypes=(elemType1, elemType2))
                del mySketch

    # rebuild assembly sets as part sets and surfaces
    # loop over assembly sets
    for setName in myAssembly.sets.keys():
        partName = setName.split('_')[1]+'_Geo'
        # if the set belongs to a newly created part (found with their name as they all start with the name of the scanIP mask they are built on)
        # then reads all nodes coordinates and build corresponding part set and surface
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
    
    deleteOldFeatures(myModel)
    addPartsToAssembly(myModel)

#-----------------------------------------------------
#-----------------------------------------------------       
def shellTo3DExtruGeo(myModel,extrusionDepth=5.,seedSize=0.5):
    '''
    shellTo3DExtruGeo is the function to be called from abaqus cae
    mandatory arguments:
     myModel: an abaqus model (model produced with scanIP and imported in abaqus)
    optional arguments:
     extrusionDepth: the extrusion depth (default is 5.)
     seedSize: the relative size of the new mesh points (0.5 means there will be two seeds per geometrical line ie one new element edge per old element edge at the boundaries)
    '''
    ## load needed abaqus constants
    from abaqusConstants import THREE_D,SWEEP,DEFORMABLE_BODY,ON,C3D8R,STANDARD,ENHANCED

    ## ELEMENT INTEGRATION
    elemType1 = mesh.ElemType(elemCode=C3D8R, elemLibrary=STANDARD, hourglassControl=ENHANCED)
    
    myAssembly = myModel.rootAssembly
    clearUnwantedNodes(myModel)
    myAssembly.regenerate()#needed to still have access to assembly node sets
        
    ## for each set that makes a shell, create a new part (by getting the external edges as Lines) and mesh it
    # those sets are assembly sets defined by scanIP --> loop over assembly instances and over sets in those instances
    for myInstance in myAssembly.instances.values():
        for myISet in myInstance.sets.keys():
            # find set which is a shell (each set will form a new part)
            if myISet.endswith('WITH_ZMIN'):
                # create a new sketch to create a new geometrical part
                mySketch = createSketch(myModel,myInstance.sets[myISet])
                # create new part whose name will be 'nameOfTheCorrespondingScanIPMask_Geo'
                myNewPart = myModel.Part(name=myISet.split('_')[1]+'_Geo', dimensionality=THREE_D, type=DEFORMABLE_BODY)
                myNewPart.BaseSolidExtrude(sketch=mySketch, depth=extrusionDepth)
                # assign mesh controls and seeds
                #myNewPart.setMeshControls(regions=(myNewPart.faces[0],), technique=SWEEP)
                myNewPart.seedPart(size=seedSize)#, deviationFactor=0.1, minSizeFactor=0.1)
                # create new mesh
                myNewPart.generateMesh()
                myNewPart.setElementType(regions=(myNewPart.cells[0],), elemTypes=(elemType1, ))
                del mySketch

    deleteOldFeatures(myModel)
    addPartsToAssembly(myModel)
