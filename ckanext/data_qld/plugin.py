# encoding: utf-8

import cgi
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit

import auth_functions as auth
import constants
import converters
import helpers
import logging

log = logging.getLogger(__name__)

try:
    import actions
    import datarequest_auth_functions as datareq_auth
    enable_datarequests = True
except ImportError:
    log.warn("Unable to find data request requirements, disabling")
    enable_datarequests = False

try:
    import validation
    enable_validation = True
except ImportError:
    log.warn("Unable to find validation requirements, disabling")
    enable_validation = False


class DataQldPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.IPackageController, inherit=True)
    plugins.implements(plugins.IAuthFunctions)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IRoutes, inherit=True)
    plugins.implements(plugins.IResourceController, inherit=True)
    plugins.implements(plugins.IMiddleware, inherit=True)

    # IConfigurer
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
        toolkit.add_resource('fanstatic', 'data_qld')

    def update_config_schema(self, schema):
        ignore_missing = toolkit.get_validator('ignore_missing')
        schema.update({
            # This is a custom configuration option
            'ckanext.data_qld.datarequest_suggested_description': [ignore_missing, unicode],
            'ckanext.data_qld.resource_formats': [ignore_missing, unicode]
        })
        return schema

    # ITemplateHelpers
    def get_helpers(self):
        return {'data_qld_data_driven_application': helpers.data_driven_application,
                'data_qld_dataset_data_driven_application': helpers.dataset_data_driven_application,
                'data_qld_datarequest_default_organisation_id': helpers.datarequest_default_organisation_id,
                'data_qld_organisation_list': helpers.organisation_list,
                'data_qld_datarequest_suggested_description': helpers.datarequest_suggested_description,
                'data_qld_user_has_admin_access': helpers.user_has_admin_access,
                'data_qld_format_activity_data': helpers.format_activity_data,
                'get_datarequest_comments_badge': helpers.get_datarequest_comments_badge,
                'data_qld_resource_formats': helpers.resource_formats
                }

    # IValidators
    def get_validators(self):
        validators = {
            'data_qld_filesize_converter': converters.filesize_converter,
            'data_qld_filesize_formatter': converters.filesize_formatter,
        }

        if enable_validation:
            validators['data_qld_scheming_choices'] = validation.scheming_choices

        return validators

    # IPackageController
    def set_maintainer_from_author(self, entity):
        entity.author = entity.author_email
        entity.maintainer = entity.author_email
        entity.maintainer_email = entity.author_email

    def create(self, entity):
        self.set_maintainer_from_author(entity)

    def edit(self, entity):
        self.set_maintainer_from_author(entity)

    # IAuthFunctions
    def get_auth_functions(self):
        auth_functions = {'member_create': auth.member_create}

        if enable_datarequests:
            auth_functions[constants.UPDATE_DATAREQUEST] = datareq_auth.update_datarequest
            auth_functions[constants.UPDATE_DATAREQUEST_ORGANISATION] = datareq_auth.update_datarequest_organisation
            auth_functions[constants.CLOSE_DATAREQUEST] = datareq_auth.close_datarequest
            auth_functions[constants.OPEN_DATAREQUEST] = datareq_auth.open_datarequest

        return auth_functions

    # IActions
    def get_actions(self):
        if not enable_datarequests:
            return {}

        additional_actions = {
            constants.OPEN_DATAREQUEST: actions.open_datarequest,
            constants.CREATE_DATAREQUEST: actions.create_datarequest,
            constants.UPDATE_DATAREQUEST: actions.update_datarequest,
            constants.CLOSE_DATAREQUEST: actions.close_datarequest,
        }
        return additional_actions

    # IRoutes
    def before_map(self, m):
        if enable_datarequests:
            # Re_Open a Data Request
            m.connect('/%s/open/{id}' % constants.DATAREQUESTS_MAIN_PATH,
                      controller='ckanext.data_qld.controller:DataQldUI',
                      action='open_datarequest', conditions=dict(method=['GET', 'POST']))

        if enable_validation:
            m.connect('/dataset/{dataset_id}/resource/{resource_id}/%s/show/' % constants.SCHEMA_MAIN_PATH,
                      controller='ckanext.data_qld.controller:DataQldUI',
                      action='show_schema', conditions=dict(method=['GET']))

        return m

    # IResourceController
    def before_create(self, context, data_dict):
        return self.check_file_upload(data_dict)

    def before_update(self, context, current_resource, updated_resource):
        return self.check_file_upload(updated_resource)

    def check_file_upload(self, data_dict):
        # This method is to fix a bug that the ckanext-scheming creates for setting the file size of an uploaded
        # resource. Currently the actions resource_create and resource_update will only set the resource size if the
        # key does not exist in the data_dict.
        # So we will check if the resource is a file upload and remove the 'size' dictionary item from the data_dict.
        # The action resource_create and resource_update will then set the data_dict['size'] = upload.filesize if
        # 'size' not in data_dict.
        file_upload = data_dict.get(u'upload', None)
        if isinstance(file_upload, cgi.FieldStorage):
            data_dict.pop(u'size', None)

        return data_dict

    def after_create(self, context, data_dict):
        # Set the resource position order for this (latest) resource to first
        resource_id = data_dict.get('id', None)
        package_id = data_dict.get('package_id', None)
        if resource_id and package_id:
            try:
                toolkit.get_action('package_resource_reorder')(context, {'id': package_id, 'order': [resource_id]})
            except Exception, e:
                log.error(str(e))
        return data_dict

    # IMiddleware
    def make_middleware(self, app, config):
        return AuthMiddleware(app, config)


class AuthMiddleware(object):
    def __init__(self, app, app_conf):
        self.app = app

    def __call__(self, environ, start_response):
        # Redirect users to /user/reset page after submitting password reset request
        if environ['PATH_INFO'] == '/' and 'HTTP_REFERER' in environ and 'user/reset' in environ['HTTP_REFERER']:
            headers = [('Location', '/user/reset')]
            status = "302 Found"
            start_response(status, headers)
            return ['']

        return self.app(environ, start_response)
