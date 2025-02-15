# Copyright 2022 Fuzz Introspector Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Main entrypoint for OSS-Fuzz.

This script will handle most of what is needed to run the frontend within
the OSS-Fuzz environment. The steps taken are:
1) Building the necessary .jar file for the frontend code.
2) Find all fuzz targets in /out/.
3) Find all .jar files needed for the analysis.
4) Run the frontend analysis on all fuzz targets and the relevant jar files.
"""

import os
import subprocess

FI_JVM_BASE="/fuzz-introspector/frontends/java"
PLUGIN_PATH="target/ossf.fuzz.introspector.soot-1.0.jar"
CGRAPH_STR="ossf.fuzz.introspector.soot.CallGraphGenerator"

target_mvn = "mvn"


def is_jvm_frontend_built():
  if not os.path.isfile(PLUGIN_PATH):
    return False
  return True


def build_jvm_frontend():
  if not is_jvm_frontend_built():
    subprocess.check_call(f"{target_mvn} clean package -Dmaven.test.skip", shell=True)

  if not is_jvm_frontend_built():
    return False
  return True


def find_fuzz_targets(path):
  """Finds the relevant fuzz targets in `path`
  A fuzz target is identified by a file {fuzzername} containing the string
  "LLVMFuzzerTestOneInput" and a corresponding {fuzzername}.class file.

  For each fuzz target, if there is no {fuzzername}.jar then it is created.
  """
  print("Finding fuzz targets in %s" % path)
  jar_files = set()
  targets = list()
  for classfile in os.listdir(path):
    print("Checking target %s" % classfile)
    if not classfile.endswith(".class"):
      continue

    # Check if wrapper script exists and whether it has the right tag.
    wrapper_script = classfile.replace(".class", "")
    if not os.path.isfile(wrapper_script):
      continue
    with open(wrapper_script) as wrapper_script_fd:
      if 'LLVMFuzzerTestOneInput' not in wrapper_script_fd.read():
        continue

    # Create relevant .jar file if it is not there.
    jar_file = classfile.replace(".class", ".jar")
    if not os.path.exists(jar_file):
      subprocess.check_call("jar cvf %s %s" % (jar_file, classfile), shell=True)

    targets.append(classfile)
  return targets

def get_all_jar_files(path):
  """Gets all jar files of interest in path"""
  jar_files = set()
  for jarfile in os.listdir(path):
    if not jarfile.endswith(".jar"):
      continue
    if "jazzer" in jarfile:
      continue
    jar_files.add(jarfile)
  return jar_files


def run_introspector_frontend(target_class, jar_set):
  """Call into the frontend for analysing java targets. The output of this
  is a set of *.data and *.data.yaml files in the current directory.
  """
  print("Running introspector frontend on %s :: %s" % (target_class, jar_set))
  jarfile_str = ":".join(jar_set)
  cmd = [
      "java",
      "-Xmx6144M",
      "-cp",
      FI_JVM_BASE + "/" + PLUGIN_PATH,
      CGRAPH_STR,
      jarfile_str,
      target_class.replace(".class", ""),
      "fuzzerTestOneInput", # entrymethod
      "===jdk.:java.:javax.:sun.:sunw.:com.sun.:com.ibm.:com.apple.:apple.awt." # include prefix === exclude prefix
  ]

  print("Running command: [%s]" % " ".join(cmd))
  subprocess.check_call(" ".join(cmd), shell=True)


def run_analysis(path):
  if not build_jvm_frontend():
    return False

  currwd = os.getcwd()
  os.chdir(path)

  targets = find_fuzz_targets(path)
  jar_files = get_all_jar_files(path)

  for target in targets:
    run_introspector_frontend(target, jar_files)
  os.chdir(currwd)

if __name__ == "__main__":
  if 'MVN' in os.environ:
    target_mvn = os.environ['MVN']
  currdir = os.getcwd()
  mydir = os.path.dirname(os.path.abspath(__file__))
  os.chdir(mydir)
  run_analysis(os.environ['OUT'])
  os.chdir(currdir)
