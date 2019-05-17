import ckan.plugins.toolkit as toolkit
from profanity import profanity
from pylons import config
from bs4 import BeautifulSoup


def is_user_sysadmin(user=None):
    '''Returns True if authenticated user is sysadmim 

    :rtype: boolean

    '''
    if user is None:
        user = toolkit.c.userobj
    return user.sysadmin

def user_has_admin_access(include_editor_access):
    user = toolkit.c.userobj
    if is_user_sysadmin(user): 
        return True
      
    groups_admin = user.get_groups('organization', 'admin')  
    groups_editor = user.get_groups('organization', 'editor')  if include_editor_access else [] 
    groups_list = groups_admin + groups_editor
    organisation_list = [g for g in groups_list if g.type == 'organization']   
    return len(organisation_list) > 0

def data_driven_application(data_driven_application):
    '''Returns True if data_driven_application value equals yes
        Case insensitive 

    :rtype: boolean

    '''
    if data_driven_application and data_driven_application.lower() == 'yes':
        return True
    else:
        return False

def dataset_data_driven_application(dataset_id):
    '''Returns True if the dataset for dataset_id data_driven_application value equals yes
        Case insensitive 

    :rtype: boolean

    '''
    try:
        package = toolkit.get_action('package_show')(
            data_dict={'id': dataset_id})
    except toolkit.ObjectNotFound:
        return False

    return data_driven_application(package.get('data_driven_application', ''))


def datarequest_default_organisation():
    '''Returns the default organisation for data request from the config file
        Case insensitive 

    :rtype: organisation

    '''
    default_organisation = config.get('ckan.datarequests.default_organisation')
    try:
        organisation = toolkit.get_action('organization_show')(
            data_dict={
                'id':default_organisation,
                'include_datasets':False,
                'include_dataset_count':False,
                'include_extras':False,
                'include_users':False,
                'include_groups':False,
                'include_tags':False,
                'include_followers':False
            })
    except toolkit.ObjectNotFound:    
        toolkit.abort(404, toolkit._('Default Data Request Organisation not found. Please get the sysadmin to set one up'))        

    return organisation

def datarequest_default_organisation_id():
    '''Returns the default organisation id for data request from the config file

    :rtype: integer

    '''  
    organisation_id = datarequest_default_organisation().get('id')
    print('datarequest_default_organisation_id: %s', organisation_id)
    return organisation_id

def organisation_list():
    '''Returns a list of organisations with all the organisation fields 

    :rtype: Array of organisations

    '''  
    return toolkit.get_action('organization_list')(data_dict={'all_fields':True})

def datarequest_suggested_description():
    '''Returns a datarequest suggested description from admin config

    :rtype: string

    '''
    return config.get('ckanext.data_qld.datarequest_suggested_description', '')


def format_activity_data(data):
    '''Returns the activity data with actors username replaced with Publisher for non-editor/admin/sysadmin users

    :rtype: string

    '''
    if(user_has_admin_access(True)):
        return data

    soup = BeautifulSoup(data, 'html.parser')

    for actor in soup.select(".actor"):
        actor.string = 'Publisher'
        # the img element is removed from actor span so need to move actor span to the left to fill up blank space
        actor['style'] = 'margin-left:-40px' 

    return str(soup)


# COMMENTS helper functions


def threaded_comments_enabled():
    return toolkit.asbool(config.get('ckan.comments.threaded_comments', False))


def users_can_edit():
    return toolkit.asbool(config.get('ckan.comments.users_can_edit', False))


def profanity_check(cleaned_comment):
    profanity.load_words(load_bad_words())
    return profanity.contains_profanity(cleaned_comment)


def load_bad_words():
    filepath = config.get('ckan.comments.bad_words_file', None)
    if not filepath:
        # @todo: dynamically set this path
        filepath = '/usr/lib/ckan/default/src/ckanext-ytp-comments/ckanext/ytp/comments/bad_words.txt'

    f = open(filepath, 'r')
    x = f.read().splitlines()
    f.close()
    return x
