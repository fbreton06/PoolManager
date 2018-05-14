#!/usr/bin/env python
import sys, re, os, zipfile, traceback, syslog, threading
from subprocess import Popen, PIPE, STDOUT

from BaseHTTPServer import HTTPServer
from CGIHTTPServer import CGIHTTPRequestHandler
from cgi import FieldStorage

try:
    # sudo pip install matplotlib
    import matplotlib.pyplot as plt
    import numpy as np
except:
    np = None

from manager import Manager

import cgitb
cgitb.enable()

MAJOR = 0
MINOR = 1
BUILD = 5

try:
    process = Popen("cat /etc/issue", stdout=PIPE, shell=True, stderr=STDOUT)
    result = process.communicate()
    isRaspberry = result[0].startswith("Rasp")
except:
    isRaspberry = False

class Handler(CGIHTTPRequestHandler):
    SUCCESS = "Success"
    RESPATH = "resources"  + os.path.sep
    PAGES = ("status", "switch", "program", "settings", "debug")
    cgi_directories = [os.path.sep]
    def __init__(self, request, client_address, server):
        self.manager = server.manager
        CGIHTTPRequestHandler.__init__(self, request, client_address, server)

    def __reboot(self):
        os.system("sudo reboot")

    def __buildSelectOptions(self, text, tag, items):
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
        try:
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
            if index < 0:
                index = len(self.PAGES) - 1
            elif index >= len(self.PAGES):
                index = 0
            # Get CGI path
            self.cgiPath = os.path.dirname(self.translate_path(self.path))
            handle = open(os.path.join(self.cgiPath, os.pardir, "html_templates", self.PAGES[index] + ".txt"), "rt")
            html = handle.read()
            handle.close()
            # Replace field
            html = html.replace("RESPATH", self.RESPATH)
            # Do actions tha match with the current template
            html = eval("self.%s(html, form)" % self.PAGES[index])
            # Begin the response
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.send_header("Content-Length", str(html))
            self.end_headers()
            self.wfile.write(html)
        except Exception as error:
            syslog.syslog("do_POST error: %s", str(error))
            raise error

    def debug(self, html, form):
        if form.has_key("stat"):
            html += "<br>\n"
#             for day in range(len(self.manager.statistic)):

#                 if len(self.manager.statistic[day]) > 0:
#                     keys = self.manager.stats[day].keys()
#                     break
#             for key in keys:
#                 if np is None:
#                     html += "<h2>%s</h2><br>\n" % key
#                     index = (self.manager.currentStats + 1) % len(self.manager.stats) # Select older
#                     for day in range(len(self.manager.stats)):
#                         if self.manager.stats[index] is not None:
#                             if self.manager.stats[index].has_key(key):
#                                 keyStats = self.manager.stats[index][key]
#                                 if len(keyStats) > 0:
#                                     line = ""
#                                     if index == (self.manager.currentStats + 1) % len(self.manager.stats):
#                                         for x in range(1, len(keyStats)+1):
#                                             line += "%6.d " % x
#                                         line += "<br>\n"
#                                     for keyStat in keyStats:
#                                         line += "%4.1f " % keyStat
#                                     html += line + "<br><br>\n"
#                         index = (index + 1) % len(self.manager.stats)
#                 else:
#                     resource = "%s%s.jpg" % (self.RESPATH, key)
#                     index = (self.manager.currentStats + 1) % len(self.manager.stats) # Select older
#                     for day in range(len(self.manager.stats)):
#                         if self.manager.stats[index] is not None:
#                             if self.manager.stats[index].has_key(key):
#                                 keyStats = self.manager.stats[index][key]
#                                 if len(keyStats) > 0:
#                                     plt.plot(np.array(range(1, len(keyStats)+1)), np.array(keyStats))
#                         index = (index + 1) % len(self.manager.stats)
#                     plt.title(resource)
#                     plt.legend()
#                     plt.xlabel("Time: in step of %d second" % self.manager.REFRESH_TICK)
#                     plt.ylabel(key)                        
#                     plt.savefig(os.path.join(self.manager.refPath, "PoolSurvey", "cgi-bin", resource))
#                     html += "<img src=\"%s\"><br>\n" % resource
        elif form.has_key("log"):
            try:
                process = Popen("cat /var/log/syslog", stdout=PIPE, shell=True, stderr=STDOUT)
                result = process.communicate()
                html += "<font color=\"black\" size=\"1pt\"><br>"
                basename = os.path.basename(__file__)
                lines = list()
                for line in result[0].split("\n"):
                    if basename in line:
                        lines.append(line)
                print len(lines)
                if len(lines) > 100:
                    html += "<br>".join(lines[-100:])
                else:
                    html += "<br>".join(lines)
                html += "</font><br>"
            except Exception as error:
                html += "Failed to read \"/var/log/syslog\": %s" % str(error)
        else:
            html += "<br>Database:%s<br>" % self.manager.databse.html(", ")
        return html

    def status(self, html, form):
        html = html.replace("PHLEVEL", "%.1f" % self.manager.ph.read())
        html = html.replace("ORPLEVEL", "%d" % self.manager.redox.read())
        html = html.replace("TEMPERATURE", "%.1f" % self.manager.temperature.read())
        html = html.replace("PRESSION", "%.1f" % self.manager.pressure.read())
        html = html.replace("LEDPUMP", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.pump.isSwitchOn()])
        html = html.replace("LEDROBOT", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.robot.isSwitchOn()])
        html = html.replace("LEDPH", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.ph.isSwitchOn()])
        html = html.replace("LEDCL", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.redox.isSwitchOn()])
        html = html.replace("LEDFILL", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.waterlevel.isSwitchOn()])
        html = html.replace("LEDLIGHT", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.light.isSwitchOn()])
        html = html.replace("LEDOPEN", self.RESPATH + "led_green%s.png" % ["-off", ""][self.manager.curtain.isSwitchOn()])
        html = html.replace("LEDDEFAULT", self.RESPATH + "led_red%s.png" % ["-off", ""][len(self.manager.default) > 0])
        return html

    def switch(self, html, form):
        kinds = ("pump", "robot", "ph", "redox", "waterlevel")
        for kind in kinds:
            options = [False, False, False]
            if form.has_key(kind):
                mode = int(form[kind].value)
                eval("self.manager.%s.setMode(mode)" % kind)
            else:
                mode = eval("self.manager.%s.getMode()" % kind)
            assert mode >= 0 and mode < 3, "Unexpected %s mode value: %d" % (kind, mode)
            options[mode] = True
            for idx in range(len(options)):
                html = html.replace("SELECT" + kind.upper() + str(idx), ["","selected"][options[idx]])
        if form.has_key("light.x"):
            self.manager.light.switchToggle()
        html = html.replace("LIGHTSWITCH", self.RESPATH + "light%s.png" % ["OFF", "ON"][self.manager.light.isSwitchOn()])
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
        if self.manager.temperature.isNoneMode():
            self.manager.pump.fullAuto = False
        else:
            if form.has_key("x") and form.has_key("y"):
                self.manager.pump.fullAuto = not self.manager.pump.fullAuto
        html = html.replace("SCHEDCHECK", ["", "checked=\"checked\""][self.manager.pump.fullAuto])
        if self.manager.pump.fullAuto:
            html = self.__buildSelectOptions(html, "\"PumpList\">", self.manager.pump.autoPrograms)
        else:
            if form.has_key("pump+") or form.has_key("pump-"):
                assert form.has_key("StartHr") and form.has_key("StartMn") and form.has_key("StopHr") and form.has_key("StopMn"), "Unexpected pump+ error"
                entry = "%s:%s\t%s:%s" % (form["StartHr"].value, form["StartMn"].value, form["StopHr"].value, form["StopMn"].value)
                if form.has_key("pump+"):
                    self.manager.pump.appendProgram(entry)
                elif entry in self.manager.pump.programs:
                    self.manager.pump.programs.remove(entry)
            html = self.__buildSelectOptions(html, "\"PumpList\">", self.manager.pump.programs)
        # Manage robot list
        if form.has_key("robot+") or form.has_key("robot-"):
            assert form.has_key("StartHr") and form.has_key("StartMn") and form.has_key("StopHr") and form.has_key("StopMn"), "Unexpected pump+ error"
            entry = "%s:%s\t%s:%s" % (form["StartHr"].value, form["StartMn"].value, form["StopHr"].value, form["StopMn"].value)
            if form.has_key("robot+"):
                self.manager.robot.appendProgram(entry)
            elif entry in self.manager.robot.programs:
                self.manager.robot.programs.remove(entry)
        html = self.__buildSelectOptions(html, "\"RobotList\">", self.manager.robot.programs)
        return html

    def settings(self, html, form):
        # TODO
        # TODO
        # TODO enlever min/max pour ph et orp et renomer ph_... + orp_... + temp_...
        # TODO
        # TODO
        fields = ("ph_idle", "redox_idle", "temperature_winter", "pressure_max", "pressure_critical")
        if form:
            html = html.replace("UPDATE_MESSAGE", "Current version is: %d.%d.%d" % (MAJOR, MINOR, BUILD))
            if form.has_key("save"):
                for field in fields:
                    if form.has_key(field):
                        key1, key2 = field.split("_")
                        eval("self.manager.%s.%s", (key1, key2)) = form[field].value
            self.manager.database.backup()
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
            except Exception as error:
                status = "Upload or extract failed: %s" % error
                syslog.syslog("Update error: %s!" % status)
            if status == self.SUCCESS:
                try:
                    hdl = open(os.path.join(extractPath, "PoolSurvey_new", os.path.basename(__file__)), "rt")
                    text = hdl.read()
                    hdl.close()
                    major, minor, build = [int(x) for x in re.findall("\n\s*MAJOR\s*=\s*(\d+)\s*\n\s*MINOR\s*=\s*(\d+)\s*\n\s*BUILD\s*=\s*(\d+)\s*\n", text)[0]]
                    if MAJOR != major:
                        db_ini = os.path.join(extractPath, "PoolSurvey_new", self.manager.database.filename)
                        if os.path.isfile(db_ini):
                            os.remove(db_ini)
                    self.manager.stop()
                    html = html.replace("UPDATE_MESSAGE", "Update version (%d.%d.%d -> %d.%d.%d): %s!" % (MAJOR, MINOR, BUILD, major, minor, build, status))
                    if isRaspberry and self.manager.isAutoStart():
                        threading.Timer(2, self.__reboot).start()
                except Exception as error:
                    status = "Version or switch failed: %s" % error
                    syslog.syslog("Update error: %s!" % status)
            html = html.replace("UPDATE_MESSAGE", "Update version (%d.%d.%d): %s!" % (MAJOR, MINOR, BUILD, status))
        for field in fields:
            key1, key2 = field.split("_")
            html = html.replace(field.upper(), str(eval("self.manager.%s.%s" % (key1, key2))))
        return html

class Server(threading.Thread):
    def __init__(self, port, manager):
        threading.Thread.__init__(self)
        self.echo("PoolSurver %d%d%d startded for %s platform" % (MAJOR, MINOR, BUILD, ["other", "RaspberryPi"][isRaspberry]))
        self.__httpd = HTTPServer(("", port), Handler)
        self.__httpd.manager = manager
        self.echo("Serveur actif sur le port %d\nStarting server, use <Ctrl-C> to stop" % port)
        self.start()

    def stop(self):
        self.__httpd.shutdown()
        self.echo("Serveur closed")

    def echo(self, message):
        syslog.syslog(str(message))
        print message

    def run(self):
        self.__httpd.serve_forever()

if __name__ == '__main__':  
    if isRaspberry:
        args = sys.argv
    else:
        args = ["command", os.path.join(os.getcwd(), os.pardir), os.getcwd(), "db.ini"]
    if len(args) != 4:
        raise ValueError, "Unexpected number of arguments: %s" % str(args)
    server = None
    manager = None
    try:
        manager = Manager(*args[1:])
        server = Server(8888, manager)
        manager.start()
    except KeyboardInterrupt:
        if server is not None:
            server.stop()
        if manager is not None:
            manager.stop()
        sys.exit(0)
    except Exception as error:
        syslog.syslog("Server closed: %s" % str(error))
        if server is not None:
            server.stop()
        if manager is None:
            traceback.print_exc(file=open(os.path.join(os.getcwd(), "errlog.txt"), "a"))
            sys.exit(1)
        else:
            manager.stop()
            traceback.print_exc(file=open(os.path.join(manager.refPath, "errlog.txt"), "a"))
            if isRaspberry and manager.isAutoStart():
                os.system("sudo reboot")
            else:
                sys.exit(1)
