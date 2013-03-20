# Create your views here.
import os
import fs

import logging
import logging.config
from pprint import pformat

from django.http import HttpResponse
from django.template import Context, RequestContext, loader
from django.conf import settings

from bdphpcprovider.smartconnectorscheduler import mc
from bdphpcprovider.smartconnectorscheduler import models
from getresults import get_results
from bdphpcprovider.smartconnectorscheduler import hrmcstages

logger = logging.getLogger(__name__)


def index(request):
    print "language code", settings.LANGUAGE_CODE
    template = loader.get_template('index.html')
    context = RequestContext(request, {})
    if request.method == 'POST':
        input_parameters = request.POST
        stages = input_parameters['stages']
        experiment_id = input_parameters['experiment_id']
        group_id = str(input_parameters['group_id'])
        requested_stages_list=str(stages).split("'")
        STAGES = ['Create', 'Setup', 'Run', 'Terminate']

        for stage in STAGES:
            if stage in requested_stages_list:
                if  stage == 'Create':
                    number_of_cores = input_parameters['number_of_cores']
                    group_id = mc.start(['create', '-v', number_of_cores])
                    message = "Your group ID is %s" % group_id
                    callback(message, stage, group_id)
                    print "Create stage completed"
                elif stage == 'Setup':
                    mc.start(['setup', '-g', group_id])
                    message = "Setup stage completed"
                    print message
                    callback(message, stage, group_id)
                elif stage == 'Run':
                    zipped_input_dir = '%s/input.zip' % settings.BDP_INPUT_DIR_PATH
                    extracted_input_dir = '%s/%s' % (settings.BDP_INPUT_DIR_PATH, group_id)
                    print "Extracted ", extracted_input_dir
                    import base64
                    try:
                        encoded_input_dir = input_parameters['input_dir']
                        decoded_input_dir = base64.b64decode(encoded_input_dir)
                        f=open(zipped_input_dir,"wb")
                        f.write(decoded_input_dir)
                        f.close()
                        command = 'unzip -o -d %s %s' % (extracted_input_dir,
                                                         zipped_input_dir)
                        os.system(command)
                        output_dir = '%s/%s/output' % (settings.BDP_OUTPUT_DIR_PATH,
                                                group_id)

                        os.system('rm -rf %s ' % output_dir)

                        mc.start(['run',
                               '-g', group_id,
                               '-i', extracted_input_dir+"/input",
                               '-o', output_dir])

                        status = "RUNNING"
                        while status == 'RUNNING':
                            status = mc.start('check',
                              '-g', group_id,
                              '-o', output_dir)

                        hrmc_output = [f for f in os.listdir(output_dir) if os.path.isdir(output_dir)
                        and not f.endswith("_post")]

                        absolute_output_dir = "%s/%s" % (output_dir, hrmc_output[0])
                        print "Absolute path ", absolute_output_dir


                        print "Getting results"


                        get_results(experiment_id, group_id, absolute_output_dir)
                        print "Getting results done"

                        message = "Run stage completed. Results are ready"
                        print message
                        print "callback started"
                        callback(message, stage, group_id)
                        print "callback done"
                    except KeyError:
                        print 'Input directory not given.' \
                              ' Run stage is skipped'
                else:
                    mc.start(['teardown', '-g', group_id, 'yes'])
                    message = "Terminate stage completed"
                    print message
                    callback(message, stage, group_id)
        print "Done"
    return HttpResponse(template.render(context))


def callback(message, stage, group_id):
    import urllib
    import urllib2
    url = settings.MYTARDIS_HPC_RESPONSE_URL
    values = {'message': message,
              'stage': stage,
              'group_id': group_id}
    data = urllib.urlencode(values)
    req = urllib2.Request(url, data)
    response = urllib2.urlopen(req)
    the_page = response.read()


def hello(request):
    template = loader.get_template('hello.html')
    context = Context({
        'text': "world",
    })
    #print_greeting("Iman")
    #start(['create', '-v','1'])
    return HttpResponse(template.render(context))


def test_directive(request, directive_id):
    """
    Create example directives to be processed
    """
    if request.user.is_authenticated():
        directives = []
        platform = "nci"
        logger.debug("directive=%s" % directive_id)

        if directive_id == "1":
            # Instantiate a template locally, then copy to remote
            directive_name = "copy"
            logger.debug("%s" % directive_name)
            directive_args = []
            directive_args.append(
                ['local://127.0.0.1/local/greet.txt',
                    ['http://rmit.edu.au/schemas/greeting/salutation',
                        ('salutation', 'Hello Iman')]])
            directive_args.append(['hpc://ncitest.org/remote/greet.txt', []])
            directives.append((platform, directive_name, directive_args))

        elif directive_id == "2":
            # concatenate that file and another file (already remote) to form result
            directive_args = []
            directive_name = "program"
            logger.debug("%s" % directive_name)
            directive_args.append(['',
                ['http://rmit.edu.au/schemas/program', ('program', 'cat'),
                ('remotehost', '127.0.0.1')]])

            directive_args.append(['hpc://ncitest.org/remote/greet.txt',
                []])
            directive_args.append(['hpc://ncitest.org/remote/greetaddon.txt',
                []])
            directive_args.append(['hpc://ncitest.org/remote/greetresult.txt',
                []])

            directives.append((platform, directive_name, directive_args))

        elif directive_id == "3":
            # transfer result back locally.
            directive_name = "copy"
            logger.debug("%s" % directive_name)
            directive_args = []
            directive_args.append(['hpc://ncitest.org/remote/greetresult.txt',
                []])
            directive_args.append(['local://127.0.0.1/local/finalresult.txt',
                []])

            directives.append((platform, directive_name, directive_args))

        elif directive_id == "4":
            directive_name = "smartconnector1"
            logger.debug("%s" % directive_name)
            directive_args = []
            # Template from mytardis with corresponding metdata brought across
            directive_args.append(['tardis://iant@tardis.edu.au/datafile/15', []])
            # Template on remote storage with corresponding multiple parameter sets
            directive_args.append(['hpc://iant@nci.edu.au/input/input.txt',
                ['http://tardis.edu.au/schemas/hrmc/dfmeta/', ('a', 3), ('b', 4)],
                ['http://tardis.edu.au/schemas/hrmc/dfmeta/', ('a', 1), ('b', 2)],
                ['http://tardis.edu.au/schemas/hrmc/dfmeta2/', ('c', 'hello')]])
            # A file (template with no variables)
            directive_args.append(['hpc://iant@nci.edu.au/input/file.txt',
                []])
            # A set of commands
            directive_args.append(['', ['http://tardis.edu.au/schemas/hrmc/create',
                ('num_nodes', 5), ('iseed', 42)]])
            # An Example of how a nci script might work.
            directive_args.append(['',
                ['http://nci.org.au/schemas/hrmc/custom_command/', ('command', 'ls')]])

            directives.append((platform, directive_name, directive_args))


        elif directive_id == "5":
            platform = 'nectar'
            directive_name = "smartconnector_hrmc"
            logger.debug("%s" % directive_name)
            directive_args = []
            local_fs_path = os.path.join(
                'bdphpcprovider', 'smartconnectorscheduler', 'testing', 'remotesys/').decode("utf8")

            directive_args.append(['', ['http://rmit.edu.au/schemas/context1',
                                        ('number_vm_instances', 1), ('iseed', 42),
                ('VM_IMAGE', 'ami-0000000d'), ('VM_SIZE', 'm1.small'),
                ('SECURITY_GROUP', u"['ssh']"), ('USER_NAME', 'centos'), ('PASSWORD', ''),
                ('CUSTOM_PROMPT', '[smart-connector_prompt]$'),
                ('GROUP_ID_DIR', 'group_id'), ('group_id', 'c4573e9b0cc9ecf326c8729c7e928a9a'),
                ('flag', 0), ('CLOUD_SLEEP_INTERVAL', 5),
                ('setup_finished', 0), ('id', 0),
                ('PAYLOAD_DESTINATION', 'nectar@celery_payload_2'),
                ('PAYLOAD_SOURCE', 'file://127.0.0.1/local/testpayload'),
                ('local_fs_path', local_fs_path)]])
            directives.append((platform, directive_name, directive_args))


            # make the system settings, available to initial stage and merged with run_settings
        system_settings = {u'system': u'settings'}

        logger.debug("directive=%s" % directives)
        new_run_contexts = []
        for (platform, directive_name, directive_args) in directives:
            logger.debug("directive_name=%s" % directive_name)
            logger.debug("directive_args=%s" % directive_args)

            (run_settings, command_args, run_context) = hrmcstages.make_runcontext_for_directive(
                platform,
                directive_name,
                directive_args, system_settings, request.user.username)
            new_run_contexts.append(str(run_context))


    return HttpResponse("runs= %s" % pformat(new_run_contexts))



def getoutput(request, group_id, file_id):
    """ Return an output file identified by file_id"""
    # FIXME: add validation for group_id and file_id access

    output_dir = '%s/%s/output' % (settings.BDP_OUTPUT_DIR_PATH,
                                   group_id)
    hrmc_output = [f for f in os.listdir(output_dir) if os.path.isdir(output_dir)
    and not f.endswith("_post")]

    absolute_output_dir = "%s/%s" % (output_dir, hrmc_output[0])
    print "Absolute path ", absolute_output_dir

    file_text = open("%s/%s" % (absolute_output_dir, file_id)).read()
    return HttpResponse(file_text, mimetype='text/plain')
