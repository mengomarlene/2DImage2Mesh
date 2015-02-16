# 2DImage2Mesh
Procedure to CREATE A 2D MESH FROM AN IMAGE USING SCANIP AND ABAQUS ONLY

In scanIP
---------
1/ import your 2D image twice (this creates a virtual stack)
2/ create masks as if it was 3D (use option "on all slices" when possible!!)
3/ mesh your data as coarse as you can without changing the geometry (if needed up-sample the z-direction and down-sample the in-plane directions)
4/ set your masks as non-exportable
5/ in the mesh options, export shells of all your masks with zMin (i.e. the plane surface) - you have to export contact pairs between masks - you can export other node sets
!!scanIP 6 - DO NOT import contact pairs as contact but as node sets !!

6/ export the results in a inp file

In abaqus cae
-------------
7/ make sure your working directory includes the file 'sipShell2Abq2D.py', i.e. this file (or make it available in your python path)
8/ import your inp file as a model
9/ in the abaqus command line type (with nameOfYourModel the name of your model):

	myModel = mdb.models['nameOfYourModel']
	import sipShell2Abq2D
	sipShell2Abq2D.shellTo2DGeo(myModel)

What abaqus does:
	abaqus will look in your scanIP mesh for all the external edges (not only globally external but also those at contact surfaces)
	it will rebuild a geometry based on those edges, keeping them as they are
	the mesh abaqus produces seeds those edges, the coarser you can get is thus the size of your scanIp mesh
	all the node set and contact surfaces produced by scanIP are exported both in part Sets and part Surfaces

known issue: 
if the scanIP mesh used is relatively fine, abaqus won't be able to re-mesh it!! --> use an initial mesh as coarse as you can
