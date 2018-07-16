# --------------------------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See License.txt in the project root for license information.
# --------------------------------------------------------------------------------------------

from azure.cli.core.util import CLIError
from knack.log import get_logger

logger = get_logger(__name__)

# Important note: if cmd validator exists, then individual param validators will not be
# executed. See C:\git\azure-cli\env\lib\site-packages\knack\invocation.py `def _validation`


def create_args_for_complex_type(arg_ctx, dest, model_type, arguments, arg_group=None):
    '''
    Creates args that will be combined into an object by an arg validator.
    '''

    from knack.arguments import ignore_type
    from knack.introspection import option_descriptions

    def get_complex_argument_processor(model_properties, assigned_arg, model_type):
        '''
        Return a validator which will aggregate multiple arguments to one complex argument.
        '''

        def _expansion_validator_impl(namespace):
            '''
            The validator create a argument of a given type from a specific set of arguments from CLI
            command.
            :param namespace: The argparse namespace represents the CLI arguments.
            :return: The argument of specific type.
            '''

            # Get list of keys that are in the argparse namespace which match
            # the argparse names of properties that we are looking for
            matched_keys = [k for k in vars(namespace) if k in model_properties]

            # For each key, map the key's model property name to the value in the namespace
            properties = dict((model_properties[k], getattr(namespace, k)) for k in matched_keys)

            # Only continue if any of the values were specified by the user (i.e. are not None)
            if any(properties.values()):
                # Construct the complex model type
                logger.debug('building "{}" with values "{}"'.format(assigned_arg, properties))
                model = model_type(**properties)

                # Add the model object to the argparse namespace
                setattr(namespace, assigned_arg, model)

            else:
                logger.debug('not building "{}" because none of "{}" were specified'.format(assigned_arg, properties.keys()))

            # Delete all the keys that were build into the model
            for k in matched_keys:
                logger.debug('deleting key "{}"'.format(k))
                delattr(namespace, k)

        return _expansion_validator_impl

    # Fetch the documentation for model parameters first. for models, which are the classes
    # derive from msrest.serialization.Model and used in the SDK API to carry parameters, the
    # document of their properties are attached to the classes instead of constructors.
    parameter_docs = option_descriptions(model_type)

    model_properties = dict()

    for arg in arguments:
        if isinstance(arg, tuple):
            property_name, property_key = arg
        else:
            property_name = property_key = arg

        # Get the validation map from the model type in order to determine
        # whether the argument should be required
        validation = model_type._validation.get(property_name, None)  # pylint: disable=protected-access
        required = validation.get('required', False) if validation else False

        # Generate the command line argument name from the property name
        options_list = ['--' + property_key.replace('_', '-')]

        # Get the help text from the model type
        help_text = parameter_docs.get(property_name, None)

        # Create the additional command line argument
        arg_ctx.extra(
            property_key,
            required=required,
            options_list=options_list,
            arg_group=arg_group,
            help=help_text)

        model_properties[property_key] = property_name

    if dest:
        # Rename the original command line argument and ignore it (i.e. make invisible)
        # so that it does not show up on command line and does not conflict with any other
        # arguments.
        arg_ctx.argument(dest,
                         arg_type=ignore_type,
                         options_list=['--__{}'.format(dest.upper())],
                         # The argument is hidden from the command line, but its value
                         # will be populated by this validator.
                         validator=get_complex_argument_processor(model_properties, dest, model_type))


###############################################
#                sql server vnet-rule         #
###############################################


# Validates if a subnet id or name have been given by the user. If subnet id is given, vnet-name should not be provided.
def validate_subnet(cmd, namespace):
    from msrestazure.tools import resource_id, is_valid_resource_id
    from azure.cli.core.commands.client_factory import get_subscription_id

    subnet = namespace.virtual_network_subnet_id
    subnet_is_id = is_valid_resource_id(subnet)
    vnet = namespace.vnet_name

    if (subnet_is_id and not vnet) or (not subnet and not vnet):
        pass
    elif subnet and not subnet_is_id and vnet:
        namespace.virtual_network_subnet_id = resource_id(
            subscription=get_subscription_id(cmd.cli_ctx),
            resource_group=namespace.resource_group_name,
            namespace='Microsoft.Network',
            type='virtualNetworks',
            name=vnet,
            child_type_1='subnets',
            child_name_1=subnet)
    else:
        raise CLIError('incorrect usage: [--subnet ID | --subnet NAME --vnet-name NAME]')
    delattr(namespace, 'vnet_name')


###############################################
#                sql managed instance         #
###############################################


def validate_managed_instance_storage_size(namespace):
    # Validate if entered storage size value is an increment of 32 if provided
    if (not namespace.storage_size_in_gb) or (namespace.storage_size_in_gb and namespace.storage_size_in_gb % 32 == 0):
        pass
    else:
        raise CLIError('incorrect usage: --storage must be specified in increments of 32 GB')
