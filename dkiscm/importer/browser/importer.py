from five import grok
from Products.CMFCore.interfaces import ISiteRoot
from plone.directives import form
from plone.namedfile.field import NamedFile
from dkiscm.importer.interfaces import IProductSpecific
import csv
import z3c.form.button
from dkiscm.importer import MessageFactory as _
from StringIO import StringIO
from plone.dexterity.utils import createContentInContainer
from zope.component.hooks import getSite
from Products.statusmessages.interfaces import IStatusMessage
import re

grok.templatedir('templates')

def unicode_csv_reader(unicode_csv_data, dialect=csv.excel, **kwargs):
    # csv.py doesn't do Unicode; encode temporarily as UTF-8:
    csv_reader = csv.reader(utf_8_encoder(unicode_csv_data),
                            dialect=dialect, **kwargs)
    for row in csv_reader:
        # decode UTF-8 back to Unicode, cell by cell:
        yield [unicode(cell, 'utf-8') for cell in row]

def utf_8_encoder(unicode_csv_data):
    for line in unicode_csv_data:
        yield line.encode('utf-8')

def _extract_salary(orig_text):
    text = orig_text.replace(',','').replace(' ','').upper().strip()

    if not text:
        return ''

    match = re.match('RM(\d+)-RM(\d+)', text)
    if match:
        return '-'.join(match.groups())

    match = re.match('.*?RM(\d+)$', text)
    if match:
        return '< %s' % match.groups()[0]

    match = re.match('^RM(\d+).*$', text)
    if match:
        return '> %s' % match.groups()[0]

    raise Exception('Unable to parse salary "%s"' % orig_text)

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

        f = formdata['import_file'].data.decode('utf-8')
        for l in unicode_csv_reader(StringIO(f)):
            try:
                linenum = int(l[0])
            except:
                continue

            # Ignore item with blank jobcode
            if not l[2] or (l[2].upper().strip() == 'NEW'):
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

        obj.setDescription(data['description'])
    
        for k in ['job_code', 'education', 'education_description',
                  'similar_job_titles','professional_certification',
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
            'creative multimedia': 'creative-multimedia',
            'system design & development': 'system-design-development',
            'information technology': 'information-technology',
            'shared services & outsourcing': 'shared-services-outsourcing'
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
            'human resource':'human-resource',
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
            'similar_job_titles': [v.strip() for v in data[8].split(',') if v.strip()],
            'professional_certification': [v.strip() for v in (
                data[14].split(',')) if v.strip()],
            'industry_certification': [{
                'entry': data[14],
                'intermediate': '',
                'senior':'',
                'advanced': '',
                'master':''
            }],
            'salary_range': [{
                'entry': data[15].strip(),
                'intermediate': data[16].strip(),
                'senior': data[17].strip(),
                'advanced': data[18].strip(),
                'master': data[19].strip(),
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
                data[97:108],
                data[108:119]
            ]:
            skill = self._extract_skill(s)
            if skill:
                datadict['skills_competency'].append(skill)

        for s in [
                data[119:130],
                data[130:141],
                data[141:152],
                data[152:163],
                data[163:174],
                data[174:185]
            ]:
            skill = self._extract_softskill(s)
            if skill:
                datadict['softskills_competency'].append(skill)

        datadict['suitable_for_entry'] = (
            True if data[185].lower() == 'y' else False
        )

        datadict['job_demand'] = 0
        try:
            datadict['job_demand'] = int(data[186])
        except:
            pass

        datadict['job_demand_synovate2013'] = 0
        try:
            datadict['job_demand_synovate2013'] = int(data[187])
        except:
            pass


        return datadict

    def _extract_skill(self, data):
        have_val = False
        for i in data:
            if i:
                have_val = True
                break

        if not have_val:
            return None

        def _get_required(val):
            return True if val.lower().strip() == 'r' else False

        return {
                'skill':data[0],
                'entry':data[1],
                'entry_required': _get_required(data[2]),
                'intermediate':data[3],
                'intermediate_required': _get_required(data[4]),
                'senior':data[5],
                'senior_required': _get_required(data[6]),
                'advanced':data[7],
                'advanced_required': _get_required(data[8]),
                'master':data[9],
                'master_required': _get_required(data[10])
        }

    def _extract_softskill(self, data):
        have_val = False
        for i in data:
            if i:
                have_val = True
                break

        if not have_val:
            return None

        def _get_weight(val):
            if not val.strip():
                return None
            try:
                return int(val.strip())
            except:
                return None

        return {
                'skill':data[0],
                'entry':data[1],
                'entry_weight': _get_weight(data[2]),
                'intermediate': data[3],
                'intermediate_weight': _get_weight(data[4]),
                'senior':data[5],
                'senior_weight': _get_weight(data[6]),
                'advanced':data[7],
                'advanced_weight': _get_weight(data[8]),
                'master':data[9],
                'master_weight': _get_weight(data[10]),
        }
