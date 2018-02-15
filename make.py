#!/usr/bin/python
import os, sys, re, zipfile

def main(args):
    path = os.path.dirname(os.path.realpath(__file__))
    project = os.path.basename(path)
    workspace = os.path.dirname(path)
    projectnew = project + "_new"
    pathnew = os.path.join(workspace, projectnew)
    os.chdir(path)
    if not args:
        hdl = open("server.py", "rt")
        text = hdl.read()
        hdl.close()
        begin, number, end = re.findall("(\n\s*BUILD\s*=\s*)(\d+)(\s*\n)", text)[0]
        hdl = open("server_new.py", "wt+")
        hdl.write(text.replace(begin+number+end,begin+str(int(number) + 1)+end))
        hdl.close()
        os.remove("server.py")
        os.rename("server_new.py", "server.py")
    os.system("rm -frd %s" % os.path.join(path, project))
    os.chdir(workspace)
    os.system("cp -fr %s %s" % (project, projectnew))
    os.chdir(pathnew)
    os.system("find . -name \"*.pyc\" -type f -delete")
    os.system("rm -f make.py")
    os.system("rm -f .gitignore")
    os.system("rm -frd .git")
    hdl = open("server.py", "rt")
    text = hdl.read()
    hdl.close()
    major, minor, build = [int(x) for x in re.findall("\n\s*MAJOR\s*=\s*(\d+)\s*\n\s*MINOR\s*=\s*(\d+)\s*\n\s*BUILD\s*=\s*(\d+)\s*\n", text)[0]]
    target = "%s_%d_%d_%d.zip" % (project, major, minor, build)
    os.chdir(workspace)
    os.system("zip -9 -r %s ./%s" % (target, projectnew))
    os.system("rm -frd %s" % pathnew)
    print "Build of \"%s\" is done!" % target

if __name__ == '__main__':
    main(sys.argv[1:])
