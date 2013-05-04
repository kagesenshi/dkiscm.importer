from collective.grok import gs
from dkiscm.importer import MessageFactory as _

@gs.importstep(
    name=u'dkiscm.importer', 
    title=_('dkiscm.importer import handler'),
    description=_(''))
def setupVarious(context):
    if context.readDataFile('dkiscm.importer.marker.txt') is None:
        return
    portal = context.getSite()

    # do anything here
