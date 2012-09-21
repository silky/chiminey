import random
import os
import time
import unittest
from flexmock import flexmock
import logging
import logging.config
import paramiko
import json
import random


from simplepackage import _create_cloud_connection
from simplepackage import setup_multi_task
from simplepackage import prepare_multi_input
from simplepackage import create_environ
from simplepackage import run_multi_task
from simplepackage import packages_complete
from simplepackage import collect_instances
from simplepackage import destroy_environ
from simplepackage import NodeState

import simplepackage

from libcloud.compute.drivers.ec2 import EucNodeDriver


logger = logging.getLogger(__name__)

from smartconnector import Stage
from smartconnector import SequentialStage
from smartconnector import SmartConnector
from smartconnector import Configure, Create, Run, Check, Teardown, ParallelStage


from hrmcconnectors import Setup
from filesystem import FileElement
from filesystem import FileSystem

class CounterStage(Stage):

    def __init__(self, context):
        context['count'] = 0

    def triggered(self, context):
        count = context['count']
        return (count < 10)

    def process(self, context):

        self.count = context['count']
        self.count += 1

    def output(self, context):
        context['count'] = self.count


class TestStage(Stage):
    """ Basic stage with counter for testing """

    def __init__(self, context, key="teststage"):
        self.must_trigger = True
        self.test_count = 0
        self.key = key
        context[key] = 0

    def triggered(self, context):
        return self.must_trigger

    def process(self, context):
        pass

    def output(self, context):
        context[self.key] += 1
        pass


class SetupStageTests(unittest.TestCase):

    def test_simple(self):
        # IanT, See this comment
        #consider revising this test. FileElement is located in filesystem.py
        # for now, FileElement is still available in hrmcconnectors
        import hrmcconnectors 
        group_id = 'kjdfashkadjfghkjadzfhgkdfasj'
        f1 = hrmcconnectors.FileElement()
        f1.create(json.dumps({'group_id':group_id}))
        fs = hrmcconnectors.FileSystem()
        fs.create("/config.sys",f1)
        context = {'filesys':fs}
        s1 = Setup()
        self.assertEquals(s1.triggered(context), True)
        self.assertEquals(s1.group_id, group_id)


 



class FileSystemTests(unittest.TestCase):
    
    def setUp(self):
        pass
    
    def test_create(self):
        file_element =  FileElement("test_file")
        file_element_content = "hello\n" + "iman\n" +"and\n"+"seid\n"
        file_element.create(file_element_content)
        self.assertEquals(file_element_content, file_element.content)
        
        global_filesystem = '/home/iyusuf/test_globalFS'
        local_filesystem = 'test_localFS'
        filesystem = FileSystem(global_filesystem, local_filesystem)
        filesystem.create(local_filesystem, file_element)
        
        absolute_path_file = global_filesystem + "/" + local_filesystem + "/"+ file_element.name
        self.assertTrue(os.path.exists(absolute_path_file))
        
    def test_update(self):
        global_filesystem = '/home/iyusuf/test_globalFS'
        local_filesystem = 'test_localFS'
        filesystem = FileSystem(global_filesystem, local_filesystem)
        
        updated_file_element =  FileElement("test_file")
        updated_file_element_content = "New Greetings\n" + "iman\n" +"and\n"+"seid\n"
        updated_file_element.create(updated_file_element_content)
        
        has_updated = filesystem.update(local_filesystem, updated_file_element)
        self.assertTrue(has_updated)
        
        updated_file_element.name = "unknown_file"
        has_updated = filesystem.update(local_filesystem, updated_file_element)
        self.assertFalse(has_updated)
        
      
    """
     def test_simpletest(self):
        fsys = FileSystem()
        
        f1 = FileElement("c")
        fsys.create("a/b",f1)
        
        f3 = fsys.retrieve("a/b/c")        
        line = f3.retrieve_line(2)
        print line
        
        f2 = FileElement("c")
        lines = ["hello","iman"]
        f2.create(lines)
        
        fsys.update("a/b",f2) #whole repace

        fsys.update("a/b/d",f2)
        
        fsys.delete("a/b/c")
        #assert statement
    """
        
class ConnectorTests(unittest.TestCase):


    def setUp(self):
        pass

    def test_simple_looper(self):
        """
        Creates a simple 0-10 counter from looping stage
        """

        context = {}
        s = CounterStage(context)
        while s.triggered(context):
            s.process(context)
            s.output(context)

        self.assertEquals(context['count'],10)

    def test_smart_connector(self):
        """
        Creates a simple smart connector
        """
        context = {}
        s1 = TestStage(context)
        ss1 = SmartConnector(s1)
        ss1.process(context)
        self.assertEquals(context,{'teststage':1})

    def test_seq_stage(self):
        """
        Creates a sequential Stage
        """
        context = {}
        s1 = TestStage(context)
        s2 = TestStage(context)
        s3 = TestStage(context)
        s4 = TestStage(context)
        s5 = TestStage(context)

        # whether we will drop out straight away or continue.

        finished = TestStage(context,"finished")

        # how to convert input to output
        convert = TestStage(context,"convert")

        ss1 = SequentialStage([s1, finished, convert,
                               s2, finished, convert,
                               s3, finished, convert,
                               s4, finished, convert])

        ss1.process(context)
        self.assertEquals(context,{'finished': 4, 'convert': 4, 'teststage': 4})

    def test_seedrun(self):
        """
        Creates a single multi-seed run through
        """
        context = {}
        run = TestStage(context)
        configure = Configure()
        create =  Create()
        setup = Setup()
        run = Run()
        check = Check()
        teardown = Teardown()

        seed_run = SequentialStage([configure, create, setup, run, check, teardown])

        seed_run.process(context)
        # TODO: check state of config

    def test_seed_component(self):

        context = {}
        run = TestStage(context)
        configure = Configure()
        create = Create()
        setup = Setup()
        run = Run()
        check = Check()
        teardown = Teardown()

        seed_run = SequentialStage([configure, create, setup, run, check, teardown])

        seed_run.process(context)

    def test_daisychain(self):

        # each accepts a filesystem and either uses or creates sub filesystem
        # each accepts a context and can change as needed.
        context = {}

        s1 = TestStage(context)
        s2 = TestStage(context)
        s3 = TestStage(context)
        s4 = TestStage(context)

        p = ParallelStage()
        s = SequentialStage([s1,s2,s3,s4])



class CloudTests(unittest.TestCase):
    # TODO: Tests only the most basic run throughs of the operations with
    # single nodes. Expand to include multiple nodes, exceptions thrown
    # and return real results from paramiko and cloud calls to validate.

    def setUp(self):
        logging.config.fileConfig('logging.conf')
        self.vm_size = 100
        self.image_name = "ami-0000000d"  # FIXME: is hardcoded in
                                          # simplepackage
        self.instance_name = "foo"

        self.settings = flexmock(
            USER_NAME="accountname", PASSWORD="mypassword",
            GROUP_DIR_ID="test", EC2_ACCESS_KEY="",
            EC2_SECRET_KEY="", VM_SIZE=self.vm_size,
            PRIVATE_KEY_NAME="", PRIVATE_KEY="", SECURITY_GROUP="",
            CLOUD_SLEEP_INTERVAL=0, GROUP_ID_DIR="", DEPENDS=('a',),
            DEST_PATH_PREFIX="package", PAYLOAD_CLOUD_DIRNAME="package",
            PAYLOAD_LOCAL_DIRNAME="", COMPILER="g77", PAYLOAD="payload",
            COMPILE_FILE="foo", MAX_SEED_INT=100, RETRY_ATTEMPTS = 3,
            OUTPUT_FILES=['a', 'b'])

    def test_create_connection(self):

        # Make fake ssh connection
        # TODO: should make multiple return values to simulate all the
        # correct input/output responses

        exec_mock = ["", flexmock(readlines=lambda: ["done\n"]), ""]

        fakessh = flexmock(
            load_system_host_keys=lambda x: True,
            set_missing_host_key_policy=lambda x: True,
            connect=lambda ipaddress, username, password, timeout: True,
            exec_command=lambda command: exec_mock)

        # and use fake for paramiko
        flexmock(paramiko).should_receive('SSHClient').and_return(fakessh)

        # Make fake cloud connection
        fakeimage = flexmock(id=self.image_name)
        fakesize = flexmock(id=self.vm_size)
        fakenode_state1 = flexmock(name="foo",
                                   state=NodeState.PENDING,
                                   public_ips=[1])
        fakenode_state2 = flexmock(name="foo",
                                   state=NodeState.RUNNING,
                                   public_ips=[1])

        fakecloud = flexmock(
            found=True,
            list_images=lambda: [fakeimage],
            list_sizes=lambda: [fakesize],
            create_node=lambda
                name, size, image,
                ex_keyname,
                ex_securitygroup: fakenode_state1)

        fakecloud.should_receive('list_nodes') \
            .and_return((fakenode_state1,)) \
            .and_return((fakenode_state2,))

        flexmock(EucNodeDriver).new_instances(fakecloud)

        self.assertEquals(create_environ(1, self.settings), None)

    def test_setup_multi_task(self):

        logger.debug("test_setup_multi_tasks")

        group_id = "sq42kdjshasdkjghauiwytuiawjmkghasjkghasg"

        # Fake channel for communicating with server vida socket interface
        fakechan = flexmock(send=lambda str: True)
        fakechan.should_receive('recv') \
            .and_return('foo [%s@%s ~]$ ' % (self.settings.USER_NAME,
                                             self.instance_name)) \
            .and_return('bar [root@%s %s]# ' % (self.instance_name,
                                                self.settings.USER_NAME)) \
            .and_return('baz [%s@%s ~]$ ' % (self.settings.USER_NAME,
                                             self.instance_name))
        fakechan.should_receive('close').and_return(True)

        exec_mock = ["", flexmock(readlines=lambda: ["done\n"]), ""]

        # Make fake ssh connection
        fakessh1 = flexmock(
            load_system_host_keys=lambda x: True,
            set_missing_host_key_policy=lambda x: True,
            connect=lambda ipaddress, username, password, timeout: True,
            exec_command=lambda command: exec_mock)

        # Make fake sftp connection
        fakesftp = flexmock(get=lambda x, y: True, put=lambda x, y: True)

        exec_ret = ["", flexmock(readlines=lambda: ["exists\n"]), ""]
        # Make second fake ssh connection  for the individual setup operation
        fakessh2 = flexmock(load_system_host_keys=lambda x: True,
                        set_missing_host_key_policy=lambda x: True,
                        connect=lambda
                            ipaddress, username,
                            password, timeout: True,
                        exec_command=lambda command: exec_ret,
                        invoke_shell=lambda: fakechan,
                        open_sftp=lambda: fakesftp)

        # and use fake for paramiko
        flexmock(paramiko).should_receive('SSHClient') \
            .and_return(fakessh1) \
            .and_return(fakessh2)

        # Make fake cloud connection
        fakeimage = flexmock(id=self.image_name)
        fakesize = flexmock(id=self.vm_size)
        fakenode_state1 = flexmock(name="foo",
                                   state=NodeState.PENDING,
                                   public_ips=[1])
        fakenode_state2 = flexmock(name="foo",
                                   state=NodeState.RUNNING,
                                   public_ips=[1])

        fakecloud = flexmock(
            found=True,
            list_images=lambda: [fakeimage],
            list_sizes=lambda: [fakesize],
            create_node=lambda
                        name, size, image, ex_keyname,
                        ex_securitygroup: fakenode_state1)

        fakecloud.should_receive('list_nodes') \
            .and_return((fakenode_state1,)) \
            .and_return((fakenode_state2,))

        flexmock(EucNodeDriver).new_instances(fakecloud)

        self.assertEquals(setup_multi_task(group_id, self.settings), None)

    def test_prepare_multi_input(self):

        logger.debug("test_prepare_multi_input")

        # Make fake sftp connection
        fakesftp = flexmock(put=lambda x, y: True)

        exec_ret = ["", flexmock(readlines=lambda: ["exists\n"]), ""]
        # Make fake ssh connection
        fakessh1 = flexmock(load_system_host_keys=lambda x: True,
                        set_missing_host_key_policy=lambda x: True,
                        connect=lambda
                            ipaddress, username,
                            password, timeout: True,
                        exec_command=lambda command: exec_ret,
                        open_sftp=lambda: fakesftp)

        flexmock(random).should_receive('randrange').and_return(42)

        # and use fake for paramiko
        flexmock(paramiko).should_receive('SSHClient').and_return(fakessh1)

        # Make fake cloud connection
        fakeimage = flexmock(id=self.image_name)
        fakesize = flexmock(id=self.vm_size)
        fakenode_state1 = flexmock(name="foo",state=NodeState.RUNNING,public_ips=[1])

        fakecloud = flexmock(
            found = True,
            list_images = lambda: [fakeimage],
            list_sizes = lambda: [fakesize],
            create_node = lambda name, size, image, ex_keyname, ex_securitygroup: fakenode_state1)

        fakecloud.should_receive('list_nodes').and_return((fakenode_state1,))
        flexmock(os).should_receive('listdir').and_return(['mydirectory'])

        flexmock(EucNodeDriver).new_instances(fakecloud)


        self.assertEquals(prepare_multi_input("foobar","",self.settings, None),None)



    def test_run_multi_task(self):
        logger.debug("test_prepare_multi_input")

        # Make fake ssh connection
        fakessh1 = flexmock(load_system_host_keys= lambda x: True,
                        set_missing_host_key_policy= lambda x: True,
                        connect= lambda ipaddress, username, password, timeout: True,
                        exec_command = lambda command: ["",flexmock(readlines = lambda: ["exists\n"]),""],
                        )

        # and use fake for paramiko
        flexmock(paramiko).should_receive('SSHClient').and_return(fakessh1)

        # Make fake cloud connection
        fakeimage = flexmock(id=self.image_name)
        fakesize = flexmock(id=self.vm_size)
        fakenode_state1 = flexmock(name="foo",state=NodeState.RUNNING,public_ips=[1])

        fakecloud = flexmock(
            found = True,
            list_images = lambda: [fakeimage],
            list_sizes = lambda: [fakesize],
            create_node = lambda name,size,image,ex_keyname,ex_securitygroup: fakenode_state1)

        fakecloud.should_receive('list_nodes').and_return((fakenode_state1,))
        flexmock(os).should_receive('listdir').and_return(['mydirectory'])
        flexmock(time).should_receive('sleep')

        flexmock(EucNodeDriver).new_instances(fakecloud)

        flexmock(simplepackage).should_receive('_get_package_pid') \
            .and_return("1") \
            .and_return(None) \
            .and_return("1")

        res = run_multi_task("foobar","",self.settings)
        self.assertEquals(res.values(),[['1']])

    def test_packages_complete(self):
        logger.debug("test_packages_complete")
        # Make fake sftp connection
        fakesftp = flexmock(get=lambda x, y: True, put=lambda x, y: True)
        exec_ret = ["", flexmock(readlines=lambda: ["exists\n"]), ""]
        # Make fake ssh connection
        fakessh1 = flexmock(load_system_host_keys=lambda x: True,
                        set_missing_host_key_policy=lambda x: True,
                        connect=lambda ipaddress, username, password, timeout: True,
                        exec_command=lambda command: exec_ret,
                        open_sftp=lambda: fakesftp)
        # and use fake for paramiko
        flexmock(paramiko).should_receive('SSHClient').and_return(fakessh1)
        # Make fake cloud connection
        fakeimage = flexmock(id=self.image_name)
        fakesize = flexmock(id=self.vm_size)
        fakenode_state1 = flexmock(name="foo",state=NodeState.RUNNING,public_ips=[1])
        fakecloud = flexmock(
            found=True,
            list_images=lambda: [fakeimage],
            list_sizes=lambda: [fakesize],
            create_node=lambda name,size,image,ex_keyname,ex_securitygroup: fakenode_state1)
        fakecloud.should_receive('list_nodes').and_return((fakenode_state1,))
        flexmock(os).should_receive('listdir').and_return(['mydirectory'])
        flexmock(time).should_receive('sleep')
        flexmock(EucNodeDriver).new_instances(fakecloud)
        flexmock(simplepackage).should_receive('_get_package_pid') \
            .and_return(None)
        res = packages_complete("foobar","",self.settings)
        self.assertEquals(res, True)

    def test_collect_instances(self):
        logger.debug("test_collect_instances")
        # Make fake sftp connection
        fakesftp = flexmock(get=lambda x, y: True, put=lambda x, y: True)
        exec_ret = ["", flexmock(readlines=lambda: ["exists\n"]), ""]
        # Make fake ssh connection
        fakessh1 = flexmock(load_system_host_keys=lambda x: True,
                        set_missing_host_key_policy=lambda x: True,
                        connect=lambda ipaddress, username, password, timeout: True,
                        exec_command=lambda command: exec_ret,
                        open_sftp=lambda: fakesftp)
        # and use fake for paramiko
        flexmock(paramiko).should_receive('SSHClient').and_return(fakessh1)
        # Make fake cloud connection
        fakeimage = flexmock(id=self.image_name)
        fakesize = flexmock(id=self.vm_size)
        fakenode_state1 = flexmock(name="foo",state=NodeState.RUNNING,public_ips=[1])
        fakecloud = flexmock(
            found=True,
            list_images=lambda: [fakeimage],
            list_sizes=lambda: [fakesize],
            create_node=lambda name,size,image,ex_keyname,ex_securitygroup: fakenode_state1)
        fakecloud.should_receive('list_nodes').and_return((fakenode_state1,))
        flexmock(os).should_receive('listdir').and_return(['mydirectory'])
        flexmock(time).should_receive('sleep')
        flexmock(EucNodeDriver).new_instances(fakecloud)
        flexmock(simplepackage).should_receive('_get_package_pid') \
            .and_return(None)
        res = collect_instances(self.settings, group_id="foobar")
        logger.debug("res= %s" % res)
        self.assertEquals(len(res), 1)
        self.assertEquals(res[0].name,"foo")
        res = collect_instances(self.settings, instance_id=self.instance_name)
        self.assertEquals(len(res), 1)
        self.assertEquals(res[0].name,"foo")
        res = collect_instances(self.settings, all_VM=True)
        self.assertEquals(len(res), 1)
        self.assertEquals(res[0].name,"foo")

    def test_destroy_environ(self):
        logger.debug("test_destroy_environ")
        # first node starts terminated, and second is there after one check
        fakenode1 = flexmock(name="foo",state=NodeState.TERMINATED,public_ips=[1])
        fakenode2_state1 = flexmock(name="foo",state=NodeState.RUNNING,public_ips=[1])
        fakenode2_state2 = flexmock(name="foo",state=NodeState.TERMINATED,public_ips=[1])

        fakecloud = flexmock(
            found=True,
            destroy_node=lambda instance:  True)
        fakecloud.should_receive('list_nodes') \
            .and_return([fakenode1,fakenode2_state1]) \
            .and_return([fakenode1, fakenode2_state2])
        flexmock(EucNodeDriver).new_instances(fakecloud)
        flexmock(simplepackage).should_receive('_get_package_pid') \
            .and_return(None)
        res = destroy_environ(self.settings, [fakenode1,fakenode2_state1])

        self.assertEquals(res,None)




if __name__ == '__main__':
    unittest.main()