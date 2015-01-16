# Copyright 2012 Midokura Japan K.K.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import webob
from webob import exc

from nova.api.openstack import extensions
from nova.api.openstack import wsgi
from nova import compute
from nova import exception
from nova.i18n import _, _LE
from nova import objects
from nova.openstack.common import log as logging


LOG = logging.getLogger(__name__)


class ServerStartStopActionController(wsgi.Controller):
    def __init__(self, ext_mgr=None, *args, **kwargs):
        super(ServerStartStopActionController, self).__init__(*args, **kwargs)
        self.compute_api = compute.API()
        self.ext_mgr = ext_mgr

    def _get_instance(self, context, instance_uuid):
        try:
            attrs = ['system_metadata', 'metadata']
            return objects.Instance.get_by_uuid(context, instance_uuid,
                                                expected_attrs=attrs)
        except exception.NotFound:
            msg = _("Instance not found")
            raise webob.exc.HTTPNotFound(explanation=msg)

    @wsgi.action('os-start')
    def _start_server(self, req, id, body):
        """Start an instance."""
        context = req.environ['nova.context']
        instance = self._get_instance(context, id)
        extensions.check_compute_policy(context, 'start', instance)
        LOG.debug('start instance', instance=instance)
        try:
            self.compute_api.start(context, instance)
        except (exception.InstanceNotReady, exception.InstanceIsLocked,
                exception.InstanceInvalidState) as e:
            raise webob.exc.HTTPConflict(explanation=e.format_message())
        return webob.Response(status_int=202)

    @wsgi.action('os-stop')
    def _stop_server(self, req, id, body):
        """Stop an instance."""
        context = req.environ['nova.context']
        instance = self._get_instance(context, id)
        extensions.check_compute_policy(context, 'stop', instance)
        LOG.debug('stop instance', instance=instance)
        clean_shutdown=True
        if self.ext_mgr.is_loaded('os-force-shutdown'):
            if body['os-stop'] and 'force-shutdown' in body['os-stop']:
                force_shutdown = body['os-stop']['force-shutdown']
                if not isinstance(force_shutdown, bool):
                    msg = _LE("Argument 'force_shutdown-type' for stop must be a Boolean")
                    LOG.error(msg)
                    raise exc.HTTPBadRequest(explanation=msg)

                clean_shutdown=not force_shutdown
        try:
            self.compute_api.stop(context, instance, clean_shutdown=clean_shutdown)
        except (exception.InstanceNotReady, exception.InstanceIsLocked,
                exception.InstanceInvalidState) as e:
            raise webob.exc.HTTPConflict(explanation=e.format_message())
        return webob.Response(status_int=202)


class Server_start_stop(extensions.ExtensionDescriptor):
    """Start/Stop instance compute API support."""

    name = "ServerStartStop"
    alias = "os-server-start-stop"
    namespace = "http://docs.openstack.org/compute/ext/servers/api/v1.1"
    updated = "2012-01-23T00:00:00Z"

    def get_controller_extensions(self):
        controller = ServerStartStopActionController(self.ext_mgr)
        extension = extensions.ControllerExtension(self, 'servers', controller)
        return [extension]
