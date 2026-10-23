#!/usr/bin/env python3
"""Compile the production helper with Android fixtures and a temporary mode node."""
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'src/org/aospextended/device/performance/KProfilesSettings.java'
with tempfile.TemporaryDirectory() as tmp:
    d=Path(tmp); node=d/'kp_mode'; node.write_text('0\n')
    fixtures={
      'android/content/Context.java': 'package android.content; public class Context { public SharedPreferences prefs=new SharedPreferences(); }',
      'android/content/SharedPreferences.java': '''package android.content;
import java.util.HashMap;
public class SharedPreferences {
 public HashMap<String,Object> values=new HashMap<>();
 public boolean contains(String k) { return values.containsKey(k); }
 public String getString(String k,String def) { return values.containsKey(k)?(String)values.get(k):def; }
 public Editor edit() { return new Editor(); }
 public class Editor { public Editor putString(String k,String v) { values.put(k,v); return this; } public void apply() {} }
}''',
      'android/util/Log.java': 'package android.util; public class Log { public static int w(String tag,String msg,Throwable t) { return 0; } }',
      'org/aospextended/device/util/Utils.java': '''package org.aospextended.device.util;
import android.content.*; import java.nio.file.*; import java.io.*;
public class Utils {
 public static boolean writable=true, forceWritable; public static String readOverride;
 public static SharedPreferences getSharedPreferences(Context c) { return c.prefs; }
 public static boolean fileWritable(String p) { return forceWritable || (writable && new File(p).isFile() && new File(p).canWrite()); }
 public static String readLine(String p) {
  if(readOverride!=null) return readOverride;
  try { return Files.readString(Path.of(p)).trim(); } catch(IOException e) { return null; }
 }
}''',
    }
    fixtures['org/aospextended/device/performance/KProfilesSettings.java']=SOURCE.read_text().replace('/sys/kernel/kprofiles/kp_mode',str(node))
    fixtures['Test.java']='''
import android.content.*; import java.nio.file.*;
import org.aospextended.device.performance.KProfilesSettings;
import org.aospextended.device.util.Utils;
public class Test {
 static void check(boolean b) { if(!b) throw new AssertionError(); }
 public static void main(String[] args) throws Exception {
  Context c=new Context(); Path node=Path.of(KProfilesSettings.NODE);
  check(KProfilesSettings.isSupported()); check("0".equals(KProfilesSettings.getCurrent()));
  KProfilesSettings.restore(c); check(!c.prefs.contains(KProfilesSettings.KEY));
  check(!KProfilesSettings.setValue(c,"4")); check(!KProfilesSettings.setValue(c,"-1"));
  check(!c.prefs.contains(KProfilesSettings.KEY));
  check(KProfilesSettings.setValue(c,"3")); check("3".equals(Files.readString(node)));
  check("3".equals(c.prefs.getString(KProfilesSettings.KEY,"0")));
  Files.writeString(node,"1"); check("1".equals(KProfilesSettings.getCurrent()));
  check("3".equals(c.prefs.getString(KProfilesSettings.KEY,"0")));
  KProfilesSettings.restore(c); check("3".equals(Files.readString(node)));
  Utils.readOverride="0"; check(!KProfilesSettings.setValue(c,"2"));
  check("3".equals(c.prefs.getString(KProfilesSettings.KEY,"0"))); Utils.readOverride=null;
  Utils.writable=false; check(!KProfilesSettings.setValue(c,"1"));
  check("3".equals(c.prefs.getString(KProfilesSettings.KEY,"0"))); Utils.writable=true;
  Files.delete(node); check(!KProfilesSettings.isSupported());
  check(!KProfilesSettings.setValue(c,"1")); KProfilesSettings.restore(c);
  check(!Files.exists(node)); // Never create a replacement control when unsupported.
  Files.writeString(node,"bad"); check(!KProfilesSettings.isSupported());
  Files.writeString(node,"0"); c.prefs.values.put(KProfilesSettings.KEY,"bad");
  KProfilesSettings.restore(c); check("0".equals(Files.readString(node)));
  c.prefs.values.put(KProfilesSettings.KEY,1); KProfilesSettings.restore(c);
  check("0".equals(Files.readString(node)));
  // Simulate a disappearing/non-writable control after initial support checks.
  Files.delete(node); Files.createDirectory(node); Utils.readOverride="0"; Utils.forceWritable=true;
  check(!KProfilesSettings.setValue(c,"1"));
  check("0".equals(c.prefs.getString(KProfilesSettings.KEY,"3")));
  System.out.println("PASS: KProfiles real Java helper IO, validation, readback, persistence, external changes and boot restore");
 }
}'''
    for name,text in fixtures.items():
        p=d/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text)
    subprocess.run(['javac','-d',str(d)]+[str(d/f) for f in fixtures],check=True)
    subprocess.run(['java','-cp',str(d),'Test'],check=True)
# Verify root-free wiring and independent visibility, not just the helper.
a='{http://schemas.android.com/apk/res/android}'
xml=ET.parse(ROOT/'res/xml/RealmeParts.xml')
pref=next(p for p in xml.iter('ListPreference') if p.get(a+'key')=='kprofiles_mode')
assert pref.get(a+'persistent')=='false' and pref.get(a+'defaultValue')=='0'
arrays=ET.parse(ROOT/'res/values/arrays.xml')
assert [v.text for v in arrays.find("string-array[@name='kprofiles_values']")]==['0','1','2','3']
activity=(ROOT/'src/org/aospextended/device/RealmeParts.java').read_text()
assert 'performance.removePreference(mGpuBoost)' in activity
assert 'performance.removePreference(mKProfiles)' in activity
assert 'performance.getPreferenceCount() == 0' in activity
assert 'KProfilesSettings.setValue(getContext(), (String) newValue)' in activity
assert 'KProfilesSettings.getCurrent()' in activity
assert 'KProfilesSettings.restore(context)' in (ROOT/'src/org/aospextended/device/BootReceiver.java').read_text()
device=ROOT.parent
init=(device/'rootdir/etc/vendor/init.sm7125.rc').read_text()
assert 'chown root system /sys/kernel/kprofiles/kp_mode' in init
assert 'chmod 0660 /sys/kernel/kprofiles/kp_mode' in init
assert 'genfscon sysfs /kernel/kprofiles/kp_mode' in (device/'sepolicy/vendor/genfs_contexts').read_text()
assert 'type vendor_sysfs_kprofiles, fs_type, sysfs_type;' in (device/'sepolicy/vendor/file.te').read_text()
assert 'allow system_app vendor_sysfs_kprofiles:file { getattr open read write };' in (device/'sepolicy/vendor/system_app.te').read_text()
print('PASS: KProfiles UI, boot, resource and narrow root-free access wiring')
