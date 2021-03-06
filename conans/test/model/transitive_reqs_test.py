import unittest
from conans.test.tools import TestBufferConanOutput
from conans.paths import CONANFILE
import os
from conans.client.deps_builder import DepsBuilder, Edge
from conans.model.ref import ConanFileReference
from conans.model.options import OptionsValues
from conans.client.loader import ConanFileLoader
from conans.util.files import save
from conans.model.settings import Settings
from conans.errors import ConanException
from conans.model.requires import Requirements
from conans.client.conf import default_settings_yml
from conans.model.values import Values
from conans.model.config_dict import undefined_field, bad_value_msg
from conans.test.utils.test_files import temp_folder


class Retriever(object):
    def __init__(self, loader, output):
        self.loader = loader
        self.output = output
        self.folder = temp_folder()

    def root(self, content):
        conan_path = os.path.join(self.folder, "root")
        save(conan_path, content)
        conanfile = self.loader.load_conan(conan_path, self.output, consumer=True)
        return conanfile

    def conan(self, conan_ref, content):
        if isinstance(conan_ref, basestring):
            conan_ref = ConanFileReference.loads(conan_ref)
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        save(conan_path, content)

    def retrieve_conanfile(self, conan_ref):
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        return self.loader.load_conan(conan_path, self.output)

say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
"""

say_content2 = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.2"
"""

hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
"""

chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing"
"""

bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@diego/testing"
"""

bye_content2 = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.2@diego/testing"
"""

hello_ref = ConanFileReference.loads("Hello/1.2@diego/testing")
say_ref = ConanFileReference.loads("Say/0.1@diego/testing")
say_ref2 = ConanFileReference.loads("Say/0.2@diego/testing")
chat_ref = ConanFileReference.loads("Chat/2.3@diego/testing")
bye_ref = ConanFileReference.loads("Bye/0.2@diego/testing")


class ConanRequirementsTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, Settings.loads(""),
                                      OptionsValues.loads(""))
        self.retriever = Retriever(self.loader, self.output)
        self.builder = DepsBuilder(self.retriever, self.output)

    def root(self, content):
        root_conan = self.retriever.root(content)
        deps_graph = self.builder.load(None, root_conan)
        return deps_graph

    def test_basic(self):
        deps_graph = self.root(say_content)
        self.assertEqual(deps_graph.edges, set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.get_nodes("Say")[0]
        self.assertEqual(node.conan_ref, None)
        self._check_say(node.conanfile)

    def _check_say(self, conanfile, version="0.1", options=""):
        self.assertEqual(conanfile.version, version)
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), options)
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values_list, [])
        self.assertEqual(conanfile.requires, Requirements())

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), options)
        self.assertEqual(conaninfo.full_options.dumps(), options)
        self.assertEqual(conaninfo.requires.dumps(), "")
        self.assertEqual(conaninfo.full_requires.dumps(), "")

    def test_transitive(self):
        self.retriever.conan(say_ref, say_content)
        deps_graph = self.root(hello_content)
        self.assertEqual(2, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        say = deps_graph.get_nodes("Say")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say)})

        self.assertEqual(say.conan_ref, say_ref)
        self._check_say(say.conanfile)

    def _check_hello(self, hello, say_ref):
        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" % str(say_ref))

    def test_transitive_two_levels(self):
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)
        self.assertEqual(chat.conan_ref, None)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_diamond_no_conflict(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)
        self.assertEqual(chat.conan_ref, None)
        self.assertEqual(bye.conan_ref, bye_ref)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_simple_override(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = ("Hello/1.2@diego/testing",
               ("Say/0.2@diego/testing", "override"))
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello)})

        self._check_say(say.conanfile, version="0.2")
        self._check_hello(hello, say_ref2)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          (str(say_ref2), "override")))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@diego/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Say/0.2@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_version_requires_change(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing"

    def conan_info(self):
        hello_require = self.info.requires["Hello"]
        hello_require.version = hello_require.full_version.minor()
        say_require = self.info.requires["Say"]
        say_require.name = say_require.full_name
        say_require.version = hello_require.full_version.major()
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello)})

        self._check_say(say.conanfile, version="0.1")
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.2.Z\nSay/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_diamond_conflict(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content2)
        deps_graph = self.root(chat_content)

        self.assertIn("""Conflict in Bye/0.2@diego/testing
    Requirement Say/0.2@diego/testing conflicts with already defined Say/0.1@diego/testing
    Keeping Say/0.1@diego/testing
    To change it, override it in your base requirements""", self.output)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)
        self.assertEqual(bye.conan_ref, bye_ref)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_diamond_conflict_solved(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = ("Hello/1.2@diego/testing", "Bye/0.2@diego/testing",
                ("Say/0.2@diego/testing", "override"))
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content2)
        deps_graph = self.root(chat_content)

        self.assertIn("Hello/1.2@diego/testing requirement Say/0.1@diego/testing overriden by "
                      "your conanfile to Say/0.2@diego/testing", self.output)
        self.assertNotIn("Conflict", self.output)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref2)
        self.assertEqual(bye.conan_ref, bye_ref)

        self._check_say(say.conanfile, version="0.2")
        self._check_hello(hello, say_ref2)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref),
                                                          (str(say_ref2), "override")))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Hello/1.2@diego/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Say/0.2@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_basic_option(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
    default_options = "myoption=123"
"""
        deps_graph = self.root(say_content)
        self.assertEqual(1, len(deps_graph.nodes))
        say = deps_graph.get_nodes("Say")[0]
        self.assertEqual(deps_graph.edges, set())

        self._check_say(say.conanfile, options="myoption=123")

    def test_basic_transitive_option(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
    default_options = "myoption=123"
"""
       
        def _assert_conanfile(conanfile_content):
            self.retriever.conan(say_ref, say_content)
            deps_graph = self.root(conanfile_content)
    
            self.assertEqual(2, len(deps_graph.nodes))
            hello = deps_graph.get_nodes("Hello")[0]
            say = deps_graph.get_nodes("Say")[0]
            self.assertEqual(deps_graph.edges, {Edge(hello, say)})
    
            self.assertEqual(say.conan_ref, say_ref)
            self._check_say(say.conanfile, options="myoption=234")
    
            conanfile = hello.conanfile
            self.assertEqual(conanfile.version, "1.2")
            self.assertEqual(conanfile.name, "Hello")
            self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
            self.assertEqual(conanfile.settings.fields, [])
            self.assertEqual(conanfile.settings.values_list, [])
            self.assertEqual(conanfile.requires, Requirements(str(say_ref)))
    
            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), "")
            self.assertEqual(conaninfo.full_settings.dumps(), "")
            self.assertEqual(conaninfo.options.dumps(), "")
            self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
            self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
            self.assertEqual(conaninfo.full_requires.dumps(),
                             "%s:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d" % str(say_ref))


        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    default_options = [("Say:myoption", "234")]  # To test list definition
"""

        _assert_conanfile(hello_content)

        hello_content_tuple = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=234",  # To test tuple definition
"""
        _assert_conanfile(hello_content_tuple)

    def test_transitive_two_levels_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing"
    default_options = "Say:myoption=234"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)

        self._check_say(say.conanfile, options="myoption=234")

        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d" % str(say_ref))

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "%s:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d"
                         % (str(hello_ref), str(say_ref)))

    def test_transitive_two_levels_wrong_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing"
    default_options = "Say:myoption2=234"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)

        with self.assertRaises(ConanException) as cm:
            self.root(chat_content)
        self.assertEqual(str(cm.exception),
                         "Say/0.1@diego/testing: %s" % undefined_field("options", "myoption2",
                                                                       ['myoption']))

        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing"
    default_options = "Say:myoption=235"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)

        with self.assertRaises(ConanException) as cm:
            self.root(chat_content)
        self.assertEqual(str(cm.exception),  "Say/0.1@diego/testing: %s"
                         % bad_value_msg("options.myoption", "235", ["123", "234"]))

    def test_diamond_no_conflict_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=234"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=234"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        self._check_say(say.conanfile, options="myoption=234")
        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d")

    def test_diamond_conflict_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=234"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=123"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        self._check_say(say.conanfile, options="myoption=234")
        self.assertIn("Bye/0.2@diego/testing tried to change Say/0.1@diego/testing "
                      "option myoption to 123 but it was already assigned to 234 "
                      "by Hello/1.2@diego/testing", str(self.output).replace("\n", " "))
        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        self._check_say(say.conanfile, options="myoption=234")

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d")

    def test_diamond_conflict_options_solved(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=234"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:myoption=123"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
    default_options = "Say:myoption=123"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(self.output, "")
        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})
        self._check_say(say.conanfile, options="myoption=123")

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=123")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:e736d892567343489b1360fde797ad18a2911920")

    def test_conditional(self):
        zlib_content = """
from conans import ConanFile

class ZlibConan(ConanFile):
    name = "Zlib"
    version = "2.1"
"""
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"zip": [True, False]}

    def requirements(self):
        if self.options.zip:
            self.requires("Zlib/2.1@diego/testing")
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:zip=True"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@diego/testing"
    default_options = "Say:zip=True"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        zlib_ref = ConanFileReference.loads("Zlib/2.1@diego/testing")
        self.retriever.conan(zlib_ref, zlib_content)
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)

        deps_graph = self.root(chat_content)
        self.assertEqual(self.output, "")
        self.assertEqual(5, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        zlib = deps_graph.get_nodes("Zlib")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye), Edge(say, zlib)})

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "zip=True")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(zlib_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "zip=True")
        self.assertEqual(conaninfo.full_options.dumps(),  "zip=True")
        self.assertEqual(conaninfo.requires.dumps(), "Zlib/2.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Zlib/2.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        chat_content2 = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
    default_options = "Say:zip=False"
"""
        deps_graph = self.root(chat_content2)
        self.assertEqual(self.output, "")
        self.assertEqual(4, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello),
                                            Edge(bye, say), Edge(chat, bye)})

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "zip=False")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements())

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "zip=False")
        self.assertEqual(conaninfo.full_options.dumps(),  "zip=False")
        self.assertEqual(conaninfo.requires.dumps(), "")
        self.assertEqual(conaninfo.full_requires.dumps(), "")

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:zip=False")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "Say:zip=False")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_transitive_private(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    requires = ("Say/0.1@diego/testing", "private"),
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = ("Say/0.2@diego/testing", "private"),
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(5, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say_nodes = sorted(deps_graph.get_nodes("Say"))
        say1 = say_nodes[0]
        say2 = say_nodes[1]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say1), Edge(chat, hello),
                                            Edge(bye, say2), Edge(chat, bye)})
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say1.conanfile.name, "Say")
        self.assertEqual(say1.conanfile.version, "0.1")
        self.assertEqual(say1.conan_ref, say_ref)
        self.assertEqual(say2.conanfile.name, "Say")
        self.assertEqual(say2.conanfile.version, "0.2")
        self.assertEqual(say2.conan_ref, say_ref2)
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(bye.conanfile.name, "Bye")
        self.assertEqual(bye.conan_ref, bye_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9\n"
                         "Say/0.2@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_transitive_diamond_private(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = ("Say/0.1@diego/testing", "private"),
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@diego/testing"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing", "Bye/0.2@diego/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(5, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        bye = deps_graph.get_nodes("Bye")[0]
        say_nodes = sorted(deps_graph.get_nodes("Say"))
        say1 = say_nodes[0]
        say2 = say_nodes[1]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertTrue((deps_graph.edges == {Edge(hello, say1), Edge(chat, hello),
                                            Edge(bye, say2), Edge(chat, bye)})
                        or
                        (deps_graph.edges == {Edge(hello, say2), Edge(chat, hello),
                                            Edge(bye, say1), Edge(chat, bye)})
                        )
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say1.conanfile.name, "Say")
        self.assertEqual(say1.conanfile.version, "0.1")
        self.assertEqual(say1.conan_ref, say_ref)
        self.assertEqual(say2.conanfile.name, "Say")
        self.assertEqual(say2.conanfile.version, "0.1")
        self.assertEqual(say2.conan_ref, say_ref)
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(bye.conanfile.name, "Bye")
        self.assertEqual(bye.conan_ref, bye_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@diego/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@diego/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")


class CoreSettingsTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()

    def root(self, content, options="", settings=""):
        full_settings = Settings.loads(default_settings_yml)
        full_settings.values = Values.loads(settings)
        options = OptionsValues.loads(options)
        loader = ConanFileLoader(None, full_settings, options)
        retriever = Retriever(loader, self.output)
        builder = DepsBuilder(retriever, self.output)
        root_conan = retriever.root(content)
        deps_graph = builder.load(None, root_conan)
        return deps_graph

    def test_basic(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
    options = {"myoption": [1, 2, 3]}

    def conan_info(self):
        self.info.settings.os = "Win"
        self.info.options.myoption = "1,2,3"
"""
        deps_graph = self.root(content, options="myoption=2", settings="os=Windows")
        self.assertEqual(deps_graph.edges, set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.get_nodes("Say")[0]
        self.assertEqual(node.conan_ref, None)
        conanfile = node.conanfile

        def check(conanfile, options, settings):
            self.assertEqual(conanfile.version, "0.1")
            self.assertEqual(conanfile.name, "Say")
            self.assertEqual(conanfile.options.values.dumps(), options)
            self.assertEqual(conanfile.settings.fields, ["os"])
            self.assertEqual(conanfile.settings.values.dumps(), settings)
            self.assertEqual(conanfile.requires, Requirements())

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), "os=Win")
            self.assertEqual(conaninfo.full_settings.dumps(), settings)
            self.assertEqual(conaninfo.options.dumps(), "myoption=1,2,3")
            self.assertEqual(conaninfo.full_options.dumps(), options)
            self.assertEqual(conaninfo.requires.dumps(), "")
            self.assertEqual(conaninfo.full_requires.dumps(), "")

            self.assertEqual(conaninfo.package_id(), "6a3d66035e2dcbcfd16d5541b40785c01487c2f9")

        check(conanfile, "myoption=2", "os=Windows")

        deps_graph = self.root(content, options="myoption=1", settings="os=Linux")
        self.assertEqual(deps_graph.edges, set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.get_nodes("Say")[0]

        conanfile = node.conanfile
        check(conanfile, "myoption=1", "os=Linux")

    def test_errors(self):
        with self.assertRaisesRegexp(ConanException, "root: No subclass of ConanFile"):
            self.root("")

        with self.assertRaisesRegexp(ConanException, "root: More than 1 conanfile in the file"):
            self.root("""from conans import ConanFile
class HelloConan(ConanFile):pass
class ByeConan(ConanFile):pass""")

    def test_config(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
    options = {"myoption": [1, 2, 3]}

    def config(self):
        if self.settings.os == "Linux":
            self.options.clear()
"""
        deps_graph = self.root(content, options="myoption=2", settings="os=Windows")
        self.assertEqual(deps_graph.edges, set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.get_nodes("Say")[0]
        self.assertEqual(node.conan_ref, None)
        conanfile = node.conanfile

        def check(conanfile, options, settings):
            self.assertEqual(conanfile.version, "0.1")
            self.assertEqual(conanfile.name, "Say")
            self.assertEqual(conanfile.options.values.dumps(), options)
            self.assertEqual(conanfile.settings.fields, ["os"])
            self.assertEqual(conanfile.settings.values.dumps(), settings)
            self.assertEqual(conanfile.requires, Requirements())

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), settings)
            self.assertEqual(conaninfo.full_settings.dumps(), settings)
            self.assertEqual(conaninfo.options.dumps(), options)
            self.assertEqual(conaninfo.full_options.dumps(), options)
            self.assertEqual(conaninfo.requires.dumps(), "")
            self.assertEqual(conaninfo.full_requires.dumps(), "")

        check(conanfile, "myoption=2", "os=Windows")

        deps_graph = self.root(content, options="myoption=1", settings="os=Linux")
        self.assertEqual(deps_graph.edges, set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.get_nodes("Say")[0]

        conanfile = node.conanfile
        check(conanfile, "", "os=Linux")

    def test_config_remove(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "arch"
    options = {"arch_independent": [True, False]}

    def config(self):
        if self.options.arch_independent:
            self.settings.remove("arch")
            self.settings.os.remove("Linux")
"""
        deps_graph = self.root(content, options="arch_independent=True", settings="os=Windows")
        self.assertEqual(deps_graph.edges, set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.get_nodes("Say")[0]
        self.assertEqual(node.conan_ref, None)
        conanfile = node.conanfile

        def check(conanfile, options, settings):
            self.assertEqual(conanfile.version, "0.1")
            self.assertEqual(conanfile.name, "Say")
            self.assertEqual(conanfile.options.values.dumps(), options)
            self.assertEqual(conanfile.settings.fields, ["os"])
            self.assertEqual(conanfile.settings.values.dumps(), settings)
            self.assertEqual(conanfile.requires, Requirements())

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), settings)
            self.assertEqual(conaninfo.full_settings.dumps(), settings)
            self.assertEqual(conaninfo.options.dumps(), options)
            self.assertEqual(conaninfo.full_options.dumps(), options)
            self.assertEqual(conaninfo.requires.dumps(), "")
            self.assertEqual(conaninfo.full_requires.dumps(), "")

        check(conanfile, "arch_independent=True", "os=Windows")

        with self.assertRaises(ConanException) as cm:
            self.root(content, options="arch_independent=True", settings="os=Linux")
        self.assertIn(bad_value_msg("settings.os", "Linux", ['Android', 'Macos', "Windows"]),
                         str(cm.exception))

    def test_transitive_two_levels_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption_say": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@diego/testing"
    options = {"myoption_hello": [True, False]}
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@diego/testing"
    options = {"myoption_chat": ["on", "off"]}
"""
        output = TestBufferConanOutput()
        loader = ConanFileLoader(None, Settings.loads(""),
                                      OptionsValues.loads("Say:myoption_say=123\n"
                                                          "Hello:myoption_hello=True\n"
                                                          "myoption_chat=on"))
        retriever = Retriever(loader, output)
        builder = DepsBuilder(retriever, output)
        retriever.conan(say_ref, say_content)
        retriever.conan(hello_ref, hello_content)

        root_conan = retriever.root(chat_content)
        deps_graph = builder.load(None, root_conan)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = deps_graph.get_nodes("Hello")[0]
        say = deps_graph.get_nodes("Say")[0]
        chat = deps_graph.get_nodes("Chat")[0]
        self.assertEqual(deps_graph.edges, {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values_list, [])
        self.assertEqual(conanfile.requires, Requirements())

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "myoption_say=123")
        self.assertEqual(conaninfo.full_options.dumps(), "myoption_say=123")
        self.assertEqual(conaninfo.requires.dumps(), "")
        self.assertEqual(conaninfo.full_requires.dumps(), "")

        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(),
                         "myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "myoption_hello=True")
        self.assertEqual(conaninfo.full_options.dumps(),
                         "myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:751fd69d10b2a54fdd8610cdae748d6b22700841" % str(say_ref))

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(),
                         "myoption_chat=on\nHello:myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "myoption_chat=on")
        self.assertEqual(conaninfo.full_options.dumps(),
                         "myoption_chat=on\nHello:myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:95c360996106af45b8eec11a37df19fda39a5880\n"
                         "%s:751fd69d10b2a54fdd8610cdae748d6b22700841"
                         % (str(hello_ref), str(say_ref)))
