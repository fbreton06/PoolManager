#!/usr/bin/env python
import sys, re, os, zipfile, traceback

from BaseHTTPServer import HTTPServer
from CGIHTTPServer import CGIHTTPRequestHandler
from cgi import FieldStorage

from manager import Manager

import cgitb
cgitb.enable()

MAJOR = 0
MINOR = 1
BUILD = 2

class Handler(CGIHTTPRequestHandler):
    SUCCESS = "Success"
    RESPATH = "resources/"
    PAGES = ("status", "switch", "program", "settings")
    cgi_directories = ["/"]
    def __init__(self, request, client_address, server):
        self.manager = server.manager
        CGIHTTPRequestHandler.__init__(self, request, client_address, server)

    def buildSelectOptions(self, text, tag, items):
        begin = text.index(tag) + len(tag)
        begin = text.index("</optgroup>", begin) + len("</optgroup>")
        end = text.index("</select>", begin)
        idx = 0
        subtext = ""
        for item in items:
            subtext += "<option value=\"%d\">%s</option>\n" % (idx, item)
            idx += 1
        return text[:begin] + subtext + text[end:]

    def do_POST(self):
        if self.headers["content-type"].startswith("multipart/form-data"):
            index = 3
            form = None
        else:
            form = FieldStorage(fp=self.rfile, headers=self.headers, environ={"REQUEST_METHOD":"POST","CONTENT_TYPE":self.headers["Content-Type"]})
            ##for key in form.keys():
            ##    print key
            # Get page index
            assert form.has_key("page"), "Missing hidden page key in form"
            index = int(form["page"].value)
            # Page changed detection
            if form.has_key("next.x") and form["next.x"].value:
                index += 1
            if form.has_key("prev.x") and form["prev.x"].value:
                index -= 1
        # Read page
        assert index >= 0 and index < len(self.PAGES), "Page index %d out of bounds [0 to %d[" % (index, len(self.PAGES))
        # Get CGI path
        self.cgiPath = os.path.dirname(self.translate_path(self.path))
        handle = open(os.path.join(self.cgiPath, os.pardir, "html_templates", self.PAGES[index] + ".txt"), "rt")
        html = handle.read()
        handle.close()
        # Replace field
        html = html.replace("RESPATH", self.RESPATH)
        # Do actions tha match with the current template
        html = eval("self.%s(html, form)" % self.PAGES[index])
        if self.manager.debug_level == self.manager.DEBUG:
            html += "<br>Database:%s<br>" % self.manager.html(", ")
        # Begin the response
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(html))
        self.end_headers()
        self.wfile.write(html)

    def status(self, html, form):
        html = html.replace("PHLEVEL", "%.1f" % self.manager.ph.current)
        html = html.replace("ORPLEVEL", "%d" % self.manager.orp.current)
        html = html.replace("TEMPERATURE", "%.1f" % self.manager.temp.current)
        html = html.replace("PRESSION", "%.1f" % self.manager.pressure.current)
        html = html.replace("LEDPUMP", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.pump])
        html = html.replace("LEDROBOT", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.robot])
        html = html.replace("LEDPH", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.ph])
        html = html.replace("LEDCL", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.orp])
        html = html.replace("LEDFILL", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.filling])
        html = html.replace("LEDLIGHT", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.light])
        html = html.replace("LEDOPEN", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.state.open])
        html = html.replace("LEDDEFAULT", self.RESPATH + "led_red%s.png" % ["-off", ""][len(self.manager.default) > 0])
        return html

    def switch(self, html, form):
        kinds = ("pump", "robot", "ph", "orp", "filling")
        for kind in kinds:
            options = [False, False, False]
            if form.has_key(kind):
                mode = int(form[kind].value)
                self.manager.mode.__dict__[kind] = mode
            else:
                mode = self.manager.mode.__dict__[kind]
            assert mode >= 0 and mode < 3, "Unexpected %s mode value: %d" % (kind, mode)
            options[mode] = True
            for idx in range(len(options)):
                html = html.replace("SELECT" + kind.upper() + str(idx), ["","selected"][options[idx]])
        if form.has_key("light.x"):
            self.manager.light(not self.manager.light())
        html = html.replace("LIGHTSWITCH", self.RESPATH + "light%s.png" % ["OFF", "ON"][self.manager.light()])
        return html

    def program(self, html, form):
        # Filling Start/Stop combobox
        hour = ""
        for idx in range(24):
            hour += "<option value=\"%d\">%02d</option>" % (idx, idx)
        html = html.replace("OPTIONHOUR", hour)
        minute = ""
        for idx in range(0, 60, 15):
            minute += "\t" * 5 + "<option value=\"%d\">%02d</option>" % (idx, idx)
        html = html.replace("OPTIONMINUTE", minute)
        # TODO 2 il faudrait eviter la reinit de la combo a 00:00 a chaque POST
        # Manage pump list only in manual mode
        if form.has_key("x") and form.has_key("y"):
            self.manager.mode.program = not self.manager.mode.program
        html = html.replace("SCHEDCHECK", ["", "checked=\"checked\""][self.manager.mode.program])
        if self.manager.mode.program:
            html = self.buildSelectOptions(html, "\"PumpList\">", self.manager.program.auto)
        else:
            if form.has_key("pump+") or form.has_key("pump-"):
                assert form.has_key("StartHr") and form.has_key("StartMn") and form.has_key("StopHr") and form.has_key("StopMn"), "Unexpected pump+ error"
                entry = "%s:%s\t%s:%s" % (form["StartHr"].value, form["StartMn"].value, form["StopHr"].value, form["StopMn"].value)
                if form.has_key("pump+"):
                    self.manager.appendProgram("pumps", entry)
                elif entry in self.manager.program.pumps:
                    self.manager.program.pumps.remove(entry)
            html = self.buildSelectOptions(html, "\"PumpList\">", self.manager.program.pumps)
        # Manage robot list
        if form.has_key("robot+") or form.has_key("robot-"):
            assert form.has_key("StartHr") and form.has_key("StartMn") and form.has_key("StopHr") and form.has_key("StopMn"), "Unexpected pump+ error"
            entry = "%s:%s\t%s:%s" % (form["StartHr"].value, form["StartMn"].value, form["StopHr"].value, form["StopMn"].value)
            if form.has_key("robot+"):
                self.manager.appendProgram("robots", entry)
            elif entry in self.manager.program.robots:
                self.manager.program.robots.remove(entry)
        html = self.buildSelectOptions(html, "\"RobotList\">", self.manager.program.robots)
        return html

    def settings(self, html, form):
        fields = ("ph_min", "ph_idle", "ph_max", "orp_min", "orp_idle", "orp_max", "temp_winter", "pressure_max", "pressure_critical")
        if form:
            html = html.replace("UPDATE_MESSAGE", "Current version is: %d.%d.%d" % (MAJOR, MINOR, BUILD))
            if form.has_key("save"):
                for field in fields:
                    if form.has_key(field):
                        key1, key2 = field.split("_")
                        self.manager.__dict__[key1].__dict__[key2] = form[field].value
        else:
            # Do an update
            status = self.SUCCESS
            try:
                boundary = self.headers.plisttext.split("=")[1]
                remainbytes = int(self.headers['content-length'])
                line = self.rfile.readline()
                remainbytes -= len(line)
                if boundary not in line:
                    raise ValueError, "Content NOT begin with boundary!"
                while True:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    filenames = re.findall(r'Content-Disposition.*name="firmware"; filename="(.*)"', line)
                    if filenames:
                        break
                # Put it in CGI folder
                filename = os.path.join(self.cgiPath, filenames[0])
                line = self.rfile.readline()
                remainbytes -= len(line)
                line = self.rfile.readline()
                remainbytes -= len(line)
                try:
                    out = open(filename, 'wb')
                except IOError:
                    raise ValueError, "Can't create file to write, do you have permission to write?"
                preline = self.rfile.readline()
                remainbytes -= len(preline)
                while remainbytes > 0:
                    line = self.rfile.readline()
                    remainbytes -= len(line)
                    if boundary in line:
                        preline = preline[0:-1]
                        if preline.endswith('\r'):
                            preline = preline[0:-1]
                        out.write(preline)
                        out.close()
                        break
                    else:
                        out.write(preline)
                        preline = line
                if remainbytes < 0:
                    raise ValueError, "Unexpect Ends of data!"
                if not zipfile.is_zipfile(filename):
                    raise ValueError, "Unsupported format!"
                # Extract it at the same level that the current project
                extractPath = os.path.join(os.path.dirname(filename), os.pardir, os.pardir)
                zfile = zipfile.ZipFile(filename, "r")
                zfile.extractall(extractPath)
                zfile.close()
                os.remove(filename)
            except Exception, error:
                status = "Upload failed: %s" % error
            if status == self.SUCCESS:
                try:
                    hdl = open(os.path.join(extractPath, "PoolSurvey_new", os.path.basename(__file__)), "rt")
                    text = hdl.read()
                    hdl.close()
                    major, minor, build = [int(x) for x in re.findall("\n\s*MAJOR\s*=\s*(\d+)\s*\n\s*MINOR\s*=\s*(\d+)\s*\n\s*BUILD\s*=\s*(\d+)\s*\n", text)[0]]
                    if MAJOR != major:
                        db_ini = os.path.join(extractPath, "PoolSurvey_new", "database.ini")
                        if os.path.isfile(db_ini):
                            os.remove(db_ini)
                    self.manager.stop()
                    html = html.replace("UPDATE_MESSAGE", "Update version (%d.%d.%d -> %d.%d.%d): %s!" % (MAJOR, MINOR, BUILD, major, minor, build, status))
                    if not self.manager.SIMU:
                        os.system("sudo reboot")
                except Exception, error:
                    status = "Unsupported file: %s" % error
            if status != self.SUCCESS:
                html = html.replace("UPDATE_MESSAGE", "Update version (%d.%d.%d): %s!" % (MAJOR, MINOR, BUILD, status))
        for field in fields:
            key1, key2 = field.split("_")
            html = html.replace(field.upper(), str(self.manager.__dict__[key1].__dict__[key2]))
        return html

class Server(Manager):
    def __init__(self, port):
        try:
            Manager.__init__(self)
            print "Manager initialisation done"
            self.start()
            self.__httpd = HTTPServer(("", port), Handler)
            self.__httpd.manager = self
            print "Serveur actif sur le port %d\nStarting server, use <Ctrl-C> to stop" % port
            self.__httpd.serve_forever()
        except KeyboardInterrupt:
            self.stop()
            sys.exit(0)
        except:
            print "Serveur closed"
            self.stop()
            traceback.print_exc(file=open("/home/pi/python/errlog.txt","a"))
            if self.SIMU:
                sys.exit(1)
            else:
                os.system("sudo reboot")

if __name__ == '__main__':
    server = Server(8888)
