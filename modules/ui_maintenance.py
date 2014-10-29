# Copyright (C) 2014 Kristoffer Gronlund <kgronlund@suse.com>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#

import command
import completers as compl
from cibconfig import cib_factory
import utils
import xmlutil

_compl_actions = compl.choice(['start', 'stop', 'monitor', 'meta-data', 'validate-all',
                               'promote', 'demote', 'notify', 'reload', 'migrate_from',
                               'migrate_to', 'recover'])


class Maintenance(command.UI):
    '''
    Commands that should only be run while in
    maintenance mode.
    '''
    name = "maintenance"

    rsc_maintenance = "crm_resource -r '%s' --meta -p maintenance -v '%s'"

    def __init__(self):
        command.UI.__init__(self)

    def requires(self):
        return cib_factory.initialize()

    def _onoff(self, resource, onoff):
        if resource is not None:
            return utils.ext_cmd(self.rsc_maintenance % (resource, onoff)) == 0
        else:
            return cib_factory.create_object('property', 'maintenance-mode=%s' % (onoff))

    @command.skill_level('administrator')
    @command.completers_repeating(compl.call(cib_factory.rsc_id_list))
    def do_on(self, context, resource=None):
        '''
        Enable maintenance mode (for the optional resource or for everything)
        '''
        return self._onoff(resource, 'true')

    @command.skill_level('administrator')
    @command.completers_repeating(compl.call(cib_factory.rsc_id_list))
    def do_off(self, context, resource=None):
        '''
        Disable maintenance mode (for the optional resource or for everything)
        '''
        return self._onoff(resource, 'false')

    def _in_maintenance_mode(self, obj):
        if cib_factory.get_property("maintenance-mode") == "true":
            return True
        v = obj.meta_attributes("maintenance")
        return v and all(x == 'true' for x in v)

    def _runs_on_this_node(self, resource):
        nodes = utils.running_on(resource)
        return set(nodes) == set([utils.this_node()])

    @command.skill_level('administrator')
    @command.completers(compl.call(cib_factory.rsc_id_list), _compl_actions, compl.choice(["ssh"]))
    def do_action(self, context, resource, action, ssh=None):
        '''
        Issue action out-of-band to the given resource, making
        sure that the resource is in maintenance mode first
        '''
        obj = cib_factory.find_object(resource)
        if not obj:
            context.fatal_error("Resource not found: %s" % (resource))
        if not xmlutil.is_resource(obj.node):
            context.fatal_error("Not a resource: %s" % (resource))
        if not self._in_maintenance_mode(obj):
            context.fatal_error("Not in maintenance mode.")

        if ssh is None:
            if action not in ('start', 'monitor'):
                if not self._runs_on_this_node(resource):
                    context.fatal_error("Resource %s must be running on this node (%s)" %
                                        (resource, utils.this_node()))

            import rsctest
            return rsctest.call_resource(obj.node, action, [utils.this_node()], local_only=True)
        elif ssh == "ssh":
            import rsctest
            if action in ('start', 'promote', 'demote', 'recover', 'meta-data'):
                return rsctest.call_resource(obj.node, action,
                                             [utils.this_node()], local_only=True)
            else:
                all_nodes = cib_factory.node_id_list()
                return rsctest.call_resource(obj.node, action, all_nodes, local_only=False)
        else:
            context.fatal_error("Unknown argument: %s" % (ssh))