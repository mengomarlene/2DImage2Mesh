
#-----------------------------------------------------
def clearUnwantedNodes(model):
    from abaqusConstants import ON
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
    from abaqusConstants import ON
    ## add new parts to assembly - only after the initial instance has been deleted has they are not of the same type
    for part in model.parts.values():
       myInstaneName = part.name.split('_')[0]+'_instance'
       myAssembly.Instance(myInstaneName, part, dependent=ON)
#-----------------------------------------------------
def deleteOldFeatures(model):
    # delete old part,instance,sections,...
    del model.rootAssembly.features['PART-1-1']
    del model.parts['PART-1']
    for sName in model.sections.keys():
       del model.sections[sName]
#-----------------------------------------------------