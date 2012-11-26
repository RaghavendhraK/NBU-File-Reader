#!/usr/bin/env python

import sys

try:
	import pygtk
	#tell pyGTK, if possible, that we want GTKv2
	pygtk.require("2.0")
except:
	#Some distributions come with GTK2, but not pyGTK
	pass

try:
	from gi.repository import Gtk
except:
	print "You need to install pyGTK or GTKv2 ",
	print "or set your PYTHONPATH correctly."
	print "try: export PYTHONPATH=",
	print "/usr/local/lib/python2.2/site-packages/"
	sys.exit(1)

#now we have both gtk and gtk.glade imported
#Also, we know we are running GTK v2
import re,string,pprint,os.path
from datetime import datetime
import xml.etree.ElementTree as ET
from xml.sax.saxutils import unescape

class Message(object):
	def __init__(self, number = 0, date = 0, msg = 0,status = 0):
		self.number = number
		self.msg = msg
		self.status = status
		self.date = datetime.strftime(date,"%d.%m.%Y %H:%M:%S") if (date != 0) else 0
		self.sortDate = datetime.strftime(date,"%Y.%m.%d %H:%M:%S") if (date != 0) else 0

	def getList(self):
		return [self.number, self.msg, self.status, self.date.strftime("%d.%m.%Y %H:%M:%S"),self.date.strftime("%Y.%m.%d %H:%M:%S")]

class MessageHelperFunction(object):
	def switch(self, x):
		return {
		'inbox': 'Inbox',
		'senty': 'Sent',
		'draftsT': 'Drafts'
		}.get(x, x)

	def getStringBetween(self,string, start, end):
		pattern = start+"(.*?)"+end;
		return re.findall(pattern, string)

	def getPreDefMessages(self,predefs,folder):
		nextLine = '0A'.decode("hex")
		messages = []
		for predef in predefs:
			msgFormats =  self.getStringBetween(predef,"BEGIN:VMSG",'END:VMSG')
			for msgFormat in msgFormats:		
				msgObj = Message()
				msgObj.folder = folder
				number = self.getStringBetween(msgFormat,"TEL:\+91",'END:VCARD')
				if len(number) > 0 :
					msgObj.number = number[0].replace('~$~','')
				else :
					msgObj.number = "undefined"
				msg = self.getStringBetween(msgFormat,"BEGIN:VBODY",'END:VBODY')[0]
				status = self.getStringBetween(msgFormat,"IRMC-STATUS:",'X')[0].replace('~$~','')

				if(status == "DRAFT") :
					msgObj.status = "Draft"
				else :
					msgType = self.getStringBetween(msgFormat,"MESSAGE-TYPE:",'BEGIN')[0].replace('~$~','')
					if(msgType == "DELIVER") :
						msgObj.status = "Inbox"
					elif(msgType == "SUBMIT") :
						msgObj.status = "Sent"
					else :
						msgObj.status = "Other"
				msgObj.date = datetime.strptime(msg[8:27].strip(),"%d.%m.%Y %H:%M:%S")
				msgObj.msg = msg[30:len(msg)-3].replace('~$~',nextLine)
				messages.append(msgObj)
		return messages

	def setDistinctNumbers(self,result):
		numbers = self.getStringBetween(result,"TEL:\+91",'END:VCARD')
		self.distinctNumbers = []
		for distinctNumber in dict.fromkeys(numbers).keys():
			self.distinctNumbers.append(distinctNumber.replace('~$~',''))
		self.distinctNumbers = sorted(self.distinctNumbers, key=lambda num: (num))

	def setTheMessages(self,result):
		if (not(hasattr(self, 'messages'))):
			messages = []
			predefs = self.getStringBetween(result,"predef",'BEGIN')
			for predef in predefs:
				predef = re.escape(predef)
				predefsContent = self.getStringBetween(result,"predef"+predef,'predef')
				messages += self.getPreDefMessages(predefsContent, predef)
			self.messages = sorted(messages, key=lambda message: (message.number, message.date))

	def filterMessages(self,filterNumbers = [], filterStatus = 'All'):
		filterMsgs = []
		for msg in self.messages:
			if((len(filterNumbers) == 0 or 'All Contacts' in filterNumbers or msg.number in filterNumbers) and
				(len(filterStatus) == 0 or 'All Status' in filterStatus or msg.status in filterStatus)) :
				filterMsgs.append(msg)
		return filterMsgs

	def populateNumbersAndMsgFromXML(self,fileName):
		if (not(hasattr(self, 'messages'))):
			tree = ET.parse(fileName)
			root = tree.getroot()
			users = root.findall("user")
			if(users != None):
				self.distinctNumbers = []
				messages = []
				for user in users:
					if(int(user.attrib.get('smscount')) > 0):
						number = user.attrib.get('number')[3:]
						self.distinctNumbers.append(number)						
						for record in user.findall("record"):
							msgObj = Message()
							msgObj.number = number
							status = record.find('type').text
							if(status == "5" or status == "1") :
								msgObj.status = "Sent"							
							elif(status == "0" or status == "6") :
								msgObj.status = "Inbox"
							else :
								#Need to fix it
								#print status
								msgObj.status = "Other"
							msgObj.date = datetime.fromtimestamp(int(record.find('datetime').text[:10]))
							msgObj.msg = record.find('content').text
							if(msgObj.msg != None):
								msgObj.msg = unescape(msgObj.msg, {"&apos;": "'", "&quot;": '"'})
							messages.append(msgObj)
				self.messages = sorted(messages, key=lambda message: (message.number, message.date))

	def __init__(self, fileName):
		extension = os.path.splitext(fileName)[1]
		if(extension == ".XXOO"):
			self.populateNumbersAndMsgFromXML(fileName)
		else:
			#remove the invalid characters
			subject = open(fileName, 'r').read()
			result = filter(lambda x: x in string.printable, subject)
			res = ''
			for c in result:
				if(ord(c) == 10 or ord(c) == 13):
					res += '~$~'
				elif(ord(c)>=32):
					res += c
			#result = ''.join(c for c in result if (ord(c) >= 32))
			self.setTheMessages(res)
			self.setDistinctNumbers(res)

class appgui:	
	#populates the number
	def populate_numbers(self,numbers):
		self.numbersList.clear()
		self.numbersList.append(['All Contacts'])
		for i in numbers:
			self.numbersList.append([i])
		self.dialogWindow.iterValue = self.dialogWindow.treeView.get_model().get_iter_first()

	#populates the messages treeview
	def populate_msgs(self):
		if(hasattr(self, 'msgHelper')):
			selectedNum = self.selectedNumbers
			selectedStatus = [self.msgStatusModel[self.msgStatus.get_active()][0]]
			msgs = self.msgHelper.filterMessages(selectedNum,selectedStatus)
			self.dataTreeViewModel.clear()
			for i in msgs:
				self.dataTreeViewModel.append(i.getList())

			self.statusbar.pop(1)
			format0 = len(msgs)
			format1 = '' if format0 == 1 else 's'
			format2 = len(self.msgHelper.messages)
			format3 = '' if format2 == 1 else 's'
			statusText = "{0} message{1} showing out of {2} message{3}".format(format0,format1,format2,format3)
			self.statusbar.push(1, statusText)
			
	#event callback functions
	#winbdow destroy event
	def gtk_main_quit(self, window):
		Gtk.main_quit()

	#status Combo change event
	def on_msgStatusCombo_changed(self,widget):
		self.populate_msgs()

	#fileImport event
	def on_importFile_file_set(self, widget):
		self.selectedNumbers = []
		fileName = widget.get_filename()
		self.msgHelper = MessageHelperFunction(fileName)
		numbers = self.msgHelper.distinctNumbers
		self.populate_numbers(numbers)
		self.select_first_row()
		self.msgStatus.set_active(0)
		self.populate_msgs()

	#select ContactButton Click event
	def on_contactButton_clicked(self,widget):
		self.dialogWindow.show_all()
		self.dialogWindow.run()

	def select_first_row(self):
		if(self.dialogWindow.iterValue != None):
			self.dialogWindow.treeViewSelection.select_iter(self.dialogWindow.iterValue)

	def on_selectContactDialog_response(self, dialogWindow, response):
		if(response == 1) :
			self.dialogWindow.hide()
			self.dialogWindow.treeViewSelection.unselect_all()
			if(hasattr(self, 'tree_iter') and len(self.tree_iter) > 0):
				for tree_iter in self.tree_iter:
					self.dialogWindow.treeViewSelection.select_iter(tree_iter)
			else :
				self.select_first_row()
		else :
			(model, pathlist) = self.dialogWindow.treeViewSelection.get_selected_rows()
			self.selectedNumbers = []
			self.tree_iter = []
			if(len(pathlist) > 0):				
				for path in pathlist :
					tree_iter = model.get_iter(path)
					self.tree_iter += [tree_iter]
					value = model.get_value(tree_iter,0)
					if(value == "All Contacts"):
						self.selectedNumbers = [value]
					else:
						self.selectedNumbers += [value]
			else:
				self.select_first_row()
			self.dialogWindow.hide()
			self.populate_msgs()

	#UI initialization
	def __init__(self):		
		#UI from Glade Interface Designer
		gladefile ="NBUReader.glade"
		self.builder = Gtk.Builder()
		self.builder.add_from_file(gladefile)
		self.builder.connect_signals(self)

		#filechooser
		self.importFile = self.builder.get_object('importFile')
		
		#status combo
		self.msgStatus = self.builder.get_object("msgStatusCombo")
		self.msgStatusModel = self.msgStatus.get_model()

		#messages treeview
		self.dataTreeView = self.builder.get_object("dataTreeView")
		self.dataTreeViewModel = self.builder.get_object("messages")
		
		#ToDo:Icons are not working
		#ToDo: Select some other colors
		Gtk.rc_parse_string("""
			style "tab-close-button-style" {
				GtkTreeView::odd-row-color = "#00CBFF"
				GtkTreeView::even-row-color = "#ABABAB"
				GtkTreeView::allow-rules = 1
			}
			widget "*custom_treeview*" style "custom-treestyle"
		""")
		self.dataTreeView.set_name("custom_treeview")

		#status bar
		self.statusbar = self.builder.get_object("statusbar")

		#inital values for widgets
		self.selectedNumbers = []
		#self.populate_numbers_combo([])
		self.msgStatus.set_active(0)
		self.statusbar.push(1, "0 messages showing out of 0 messages")    	

		self.dialogWindow = self.builder.get_object("selectContactDialog")
		self.dialogWindow.treeView = self.builder.get_object("SCD-contactsTV")
		self.dialogWindow.treeViewSelection = self.builder.get_object("SCD-contactTVselection")
		self.dialogWindow.iterValue = None

		self.numbersList = self.builder.get_object('numbersList')

		self.window = self.builder.get_object("mainWindow")
		self.window.show_all()

#Start App
app = appgui()
Gtk.main()