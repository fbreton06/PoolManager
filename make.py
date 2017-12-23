#!/usr/bin/python
import os, sys, re, zipfile

def main(args):
    path = os.path.dirname(os.path.realpath(__file__))
    project = os.path.basename(path)
    workspace = os.path.dirname(path)
    if not args:
        hdl = open(os.path.join(path, "server.py"), "rt")
        text = hdl.read()
        hdl.close()
        begin, number, end = re.findall("(\n\s*BUILD\s*=\s*)(\d+)(\s*\n)", text)[0]
        hdl = open(os.path.join(path, "server2.py"), "wt+")
        hdl.write(text.replace(begin+number+end,begin+str(int(number) + 1)+end))
        hdl.close()
        os.remove(os.path.join(path, "server.py"))
        os.rename(os.path.join(path, "server2.py"), os.path.join(path, "server.py"))
    projectnew = project + "_new"
    path = os.path.join(workspace, projectnew)
    os.system("rm -r *.pyc")
    os.system("cd %s && cp -fr %s %s" % (workspace, project, projectnew))
    os.system("rm %s" % os.path.join(path, "managerSimu.py"))
    os.system("rm %s" % os.path.join(path, "make.py"))
    hdl = open(os.path.join(path, "server.py"), "rt")
    text = hdl.read()
    hdl.close()
    text = text.replace("managerSimu", "manager")
    hdl = open(os.path.join(path, "server.py"), "wt+")
    hdl.write(text)
    hdl.close()
    major, minor, build = [int(x) for x in re.findall("\n\s*MAJOR\s*=\s*(\d+)\s*\n\s*MINOR\s*=\s*(\d+)\s*\n\s*BUILD\s*=\s*(\d+)\s*\n", text)[0]]
    os.system("cd %s && zip -9 -r %s_%d_%d_%d.zip ./%s" % (workspace, project, major, minor, build, projectnew))
    os.system("rm -frd %s" % path)

if __name__ == '__main__':
    main(sys.argv[1:])
