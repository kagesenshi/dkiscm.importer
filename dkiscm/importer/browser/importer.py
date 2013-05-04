from five import grok
from Products.CMFCore.interfaces import ISiteRoot
from plone.directives import form
from plone.namedfile.field import NamedFile
from dkiscm.importer.interfaces import IProductSpecific
import csv
import z3c.form.button
from dkiscm.importer import MessageFactory as _
from cStringIO import StringIO
from plone.dexterity.utils import createContentInContainer
from zope.component.hooks import getSite
from Products.statusmessages.interfaces import IStatusMessage

grok.templatedir('templates')

class IUploadFormSchema(form.Schema):

    import_file = NamedFile(title=_('Upload CSV'))

class UploadForm(form.SchemaForm):

    name = _("Import JobMatrix from CSV")
    schema = IUploadFormSchema
    ignoreContext = True
    grok.layer(IProductSpecific)
    grok.context(ISiteRoot)
    grok.name('import_jobmatrix')
    grok.require('cmf.AddPortalContent')

    @z3c.form.button.buttonAndHandler(_("Import"), name='import')
    def import_content(self, action):
        formdata, errors = self.extractData()
        if errors:
            self.status = self.formErrorsMessage
            return

        f = formdata['import_file'].data
        reader = csv.reader(StringIO(f))
        for l in reader:
            try:
                linenum = int(l[0])
            except:
                continue
            self._import(l)
        IStatusMessage(self.request).addStatusMessage(_("Objects imported"))

    def _import(self, data):
        datadict = self._extract(data)
        self._create(datadict)

    def _create(self, data):
        container = self._find_container(
                data['industry_cluster'], 
                data['industry_cluster_title'],
                data['job_grouping'],
                data['job_grouping_title'],
        )
        obj = createContentInContainer(container, 'dkiscm.jobmatrix.job',
                                        title=data['title'],
                                        job_code=data['job_code'])
        for k in ['job_code', 'education', 'education_description',
                    'suitable_for_entry']:
            setattr(obj, k, data[k])

        for k in ['industry_certification', 'salary_range', 'skills_competency',
                'softskills_competency']:
            setattr(obj, k, data[k])

        obj.reindexObject()

    def _find_container(self, industry_cluster, industry_cluster_title,
                        job_grouping, job_grouping_title):
        site = getSite()
        if not 'cluster' in site.keys():
            site.invokeFactory(type_name='Folder', id='cluster')
            obj = site['cluster']
            obj.setTitle('Clusters')
            obj.reindexObject()
        repo = site['cluster']
        if not repo.has_key(industry_cluster):
            obj = createContentInContainer(repo, 
                    'dkiscm.jobmatrix.industrycluster',
                    title=industry_cluster
            )
            obj.setTitle(industry_cluster_title)
            obj.reindexObject()
        cluster = repo[industry_cluster]

        if not cluster.has_key(job_grouping):
            obj = createContentInContainer(cluster,
                    'dkiscm.jobmatrix.jobgroup',
                    title=job_grouping
            )
            obj.setTitle(job_grouping_title)
            obj.reindexObject()
        container = cluster[job_grouping]
        return container

    def _cluster_title_to_id(self, title):
        mapping = {
            'creative multimedia': 'creative-multimedia'
        }
        key = title.lower().strip()
        if key not in mapping:
            raise Exception('Unable to find industry cluster mapping for %s' % key)
        return mapping.get(key, '')

    def _jobgrouping_title_to_id(self, title):
        mapping = {
            'pre-production':'preproduction',
            'production':'production',
            'post-production':'postproduction',
            'architectural design':'architectural-design',
            'ic design':'ic-design',
            'system design': 'system-design',
            'software engineering': 'software-engineering',
            'software development': 'software-development',
            'database management': 'database-management',
            'technical support': 'technical-support',
            'it consulting': 'it-consulting',
            'it sales & marketing': 'it-sales-marketing',
            'it management': 'it-management',
            'contact centre':'contact-centre',
            'finance & accounting':'finance-accounting',
            'human resources':'human-resources',
            'creative content management': 'creative-content-management'
        }
        key = title.lower().strip()
        if key not in mapping:
            raise Exception('Unable to find job group mapping for %s' % key)
        return mapping.get(key, '')

    def _education_title_to_id(self, title):
        mapping = {
            'spm':'spm',
            'certificate':'certificate',
            'diploma': 'diploma',
            "bachelor's":'bachelor',
            "master's":'master'
        }
        key = title.lower().strip()
        if key not in mapping:
            raise Exception('Unable to find education id mapping for %s' % key)
        return mapping.get(key, '')

            
    def _extract(self, data):
        data = [i.strip() for i in data]
        datadict = {
            'industry_cluster_title': data[1],
            'industry_cluster': self._cluster_title_to_id(data[1]),
            'job_code': data[2],
            'job_grouping_title': data[3],
            'job_grouping': self._jobgrouping_title_to_id(data[3]),
            'title': data[4],
            'education': self._education_title_to_id(data[5]),
            'education_description': data[6],
            'description': data[7],
            'similar_job_title': data[8],
            'industry_certification': [{
                'entry': data[14],
                'intermediate': '',
                'senior':'',
                'advanced': '',
                'master':''
            }],
            'salary_range': [{
                'entry': data[15],
                'intermediate': data[16],
                'senior': data[17],
                'advanced': data[18],
                'master': data[19],
            }],
            'skills_competency': [],
            'softskills_competency': []
        }

        for s in [
                data[20:31],
                data[31:42],
                data[42:53],
                data[53:64],
                data[64:75],
                data[75:86],
                data[86:97],
                data[97:108]
            ]:
            skill = self._extract_skill(s)
            if skill:
                datadict['skills_competency'].append(skill)

        for s in [
                data[108:114],
                data[114:120],
                data[120:126],
                data[126:132],
                data[132:138],
                data[138:144]
            ]:
            skill = self._extract_softskill(s)
            if skill:
                datadict['softskills_competency'].append(skill)

        datadict['suitable_for_entry'] = (
                True if data[144].lower() == 'y' else False
        )

        return datadict

    def _extract_skill(self, data):
        have_val = False
        for i in data:
            if i:
                have_val = True
                break

        if not have_val:
            return None

        is_required = True if data[2].lower().strip() == 'r' else False

        return {
                'skill':data[0],
                'entry':data[1],
                'intermediate':data[3],
                'senior':data[5],
                'advanced':data[7],
                'master':data[9],
                'is_required': is_required
        }

    def _extract_softskill(self, data):
        have_val = False
        for i in data:
            if i:
                have_val = True
                break

        if not have_val:
            return None

        return {
                'skill':data[0],
                'col1':data[1],
                'col2':data[2],
                'col3':data[3],
                'col4':data[4],
                'col5':data[5],
                'is_required': False
        }
