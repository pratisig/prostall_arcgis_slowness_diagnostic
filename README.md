# prostall

Diagnose why ArcGIS Pro is slow on this workstation, and never report a finding the machine did
not produce. Read-only by default: nothing changes and no packet leaves the box.

An editor tells you Pro takes five minutes to open, that it hangs for two or three minutes in the
middle of an edit, and that sometimes the work she saved before the hang is gone afterwards. There
is no error message. There is no crash dump, because she ended the hang with Task Manager and that
writes no dump at all.

So you run a diagnostic. It prints a red line at the top of the report, under "act on these first",
naming a database fault as the root cause. Then you read the same check's own evidence line, three
characters further down, and it says "not observable from this workstation". The check had set its
status to Fail before the branch that would have gone and measured anything. It never contacted the
database. It could not have.

That is the defect this tool was rebuilt around. Two checks did it, they were the two most serious
lines in the report, and once an operator sees one verdict contradict its own evidence, the other
forty checks are worth nothing to him either. The three checks that could not be measured from a
workstation are gone. What replaced them is a rule the record constructor enforces: a check that
says it did not measure cannot carry a verdict, and the self-test asserts it on every status, on
every check, and across a whole run.

```
$ python prostall.py --self-test
----------------------------------------------------------------------
the status contract: a verdict needs a measurement
PASS  Pass is an accepted status
PASS  Warn is an accepted status
PASS  Fail is an accepted status
PASS  Info is an accepted status
PASS  Skipped is an accepted status
PASS  a sixth status is refused, which is what lets the summary be summed
PASS  a check saying it is not observable from the workstation cannot carry Pass  <-- pinned defect
PASS  a check saying it is not observable from the workstation cannot carry Warn  <-- pinned defect
PASS  a check saying it is not observable from the workstation cannot carry Fail  <-- pinned defect
PASS  the same text is fine on Info, which claims nothing
PASS  the same text is fine on Skipped, which claims nothing
PASS  measured=False refuses a verdict even when the text reads clean  <-- pinned defect
PASS  a fixable flag with no fix text is refused, because the summary offers it to the operator by id
PASS  an absent setting is not an unmeasured check: a settings list full of <absent> can still carry a real verdict  <-- pinned defect
...
----------------------------------------------------------------------
containment: a probe that dies is skipped, never warned
PASS  a body that throws records Skipped, not Warn: every fix gates on Warn or Fail, so Warn would let a fix fire on a determination that was never made  <-- pinned defect
PASS  the skipped record names the exception, so the operator sees which probe died
PASS  a body that emits nothing is Skipped, because saying nothing reads as saying Pass  <-- pinned defect
PASS  a body that dies after one record keeps it
PASS  a body that pairs a verdict with no measurement is contained as Skipped, not a traceback  <-- pinned defect
----------------------------------------------------------------------
the act-first roll-up owns no id list
PASS  act-first is exactly the data-loss checks that failed or warned
PASS  a data-loss check demoted to Info is not promoted back by a hardcoded id list: a roll-up that keeps a finding the check itself withdrew is a verdict nobody measured  <-- pinned defect
PASS  a failing check that does not bear on data loss stays out
PASS  and it is ordered worst first, which is the order the summary prints: a tally led by Pass buries the finding under the count of everything that was fine  <-- pinned defect
PASS  two records under one id answer with the first, not the last: the apply gate reads by id, and answering with a later Pass would let a fix run against a failure nothing withdrew  <-- pinned defect
PASS  a run whose only record is Skipped exits 0: undetermined is not a finding, and the summary says so on its own line
----------------------------------------------------------------------
path handling answers for the path, not for the host
PASS  a Windows drive is recognised on THIS host, whichever host it is: os.path is the module the host happens to run, and on Linux it finds no drive in a Windows path at all  <-- pinned defect
PASS  a Known Folder Move root is matched by its name segment, because the OneDrive variable is unset in an elevated shell  <-- pinned defect
PASS  a folder that merely starts with the word does not match
PASS  network beats OneDrive: the share latency is the problem to fix first, whether or not the folder also syncs
PASS  and exactly a kilobyte is one: the unit boundary is inclusive, so no size falls through and prints in the unit below itself  <-- pinned defect
PASS  a percent variable is expanded from the environment this run reads, never from the host process: on Linux the standard expander leaves %NAME% untouched and the check would read the wrong folder  <-- pinned defect
...
PASS  fourteen files of which all fourteen are orphaned is stale: the absolute count this replaced was dead code on a folder Pro keeps under fifty files, and reported PASS on exactly the state its own expected text calls the failure  <-- pinned defect
PASS  half stale is not stale: the trigger is proportional, not a count
PASS  and an old folder with nothing stale in it still trips the age backstop
PASS  one file under it is not: both size triggers are pinned to their numbers, so reading the constant back would not prove them
PASS  of two cache files aged twenty and forty days one is stale: the window is thirty days, and the forty-day log sitting beside them is not counted because it is not a cache file  <-- pinned defect
----------------------------------------------------------------------
every decision, on both sides of its branch
...
PASS  and the title says so, instead of printing the accusation with a PASS in front of it  <-- pinned defect
PASS  no Offline Files policy value: undetermined, and deliberately NOT inferred from the service start value, which is boot-started on stock Windows either way  <-- pinned defect
PASS  no crash dump is Info, never Pass: a hang ended from Task Manager writes no dump at all, so no dump is absence of evidence  <-- pinned defect
PASS  a portal answering in 800 ms passes, though the same 800 ms would warn against the database: the portal is allowed to be slower, and each probe carries its own allowance  <-- pinned defect
PASS  a leftover folder holding a project file warns, because it is a recovery lead for the vanished edits and not disk churn  <-- pinned defect
PASS  but a registry that could not be read at all is Info: unreadable and absent are different answers, and only one of them is a finding  <-- pinned defect
PASS  memory that could not be read is Info: without that guard a failed read computed zero and told the operator to replace memory that was probably fine  <-- pinned defect
PASS  ten gigabytes free of forty is twenty-five percent, well clear of the percentage floor, and still warns: the twenty gigabyte floor fires on its own  <-- pinned defect
PASS  fifty gigabytes free of a thousand clears the twenty gigabyte floor and warns on five percent: the ten percent floor fires on its own too  <-- pinned defect
PASS  the high performance plan passes by its identifier alone, under a name that says nothing: a managed image renames the plan, so the guid is the only part that survives  <-- pinned defect
PASS  the symbology check is always Info: no client setting was found that governs it, and none is invented here  <-- pinned defect
----------------------------------------------------------------------
no fix runs off a determination that was never made
PASS  a failing check with a fix lets that fix run
PASS  a healthy check does not
PASS  and a SKIPPED check refuses by name: its probe determined nothing, so a fix off that record acts on an answer nobody has  <-- pinned defect
PASS  a per-user fix under the wrong profile is refused rather than reporting success and changing nothing for the editor  <-- pinned defect
----------------------------------------------------------------------
a whole run against a stand-in workstation
PASS  the sick workstation reports DL-05 Fail  [got Fail]
PASS  the sick workstation reports DL-06 Fail  [got Fail]
...
PASS  every registered check produced exactly one record
PASS  not one record in a whole run pairs a verdict with text saying it measured nothing, which is the defect this tool shipped  <-- pinned defect
PASS  the data-loss block runs and prints first, ahead of every performance finding
PASS  with --apply absent the applied collection stays empty across a whole run  <-- pinned defect
PASS  the cache fix is refused while Pro is running, because clearing a live cache corrupts the session  <-- pinned defect
PASS  of three leftover session folders, the two holding a project file or a scratch table with rows in it are named, and the one holding a bare table header is not: an empty scratch geodatabase is a husk, not a recovery lead  <-- pinned defect
PASS  a file that is not a dump is not counted as one, because a Windows name filter also matches the short alias  <-- pinned defect
PASS  a project folder the walk could not open is reported as unreadable rather than as clean: a scan that returns nothing for a folder it could not read says the tree is fine when it has no idea  <-- pinned defect
PASS  and every per-user fix is refused under that profile, even with --apply, rather than reporting success and changing nothing for the editor  <-- pinned defect
PASS  nothing is promoted to the act-first list off an unread machine  <-- pinned defect
PASS  exactly three checks can still answer on a machine that reads back nothing: who is running the tool, whether Pro is open, and a graphics preference whose absence IS the finding. Every other check reports Info or Skipped rather than a verdict  <-- pinned defect
PASS  the cache folder is renamed aside, never deleted  <-- pinned defect
PASS  when there was a previous value, the undo restores that value rather than deleting the setting  <-- pinned defect
...
----------------------------------------------------------------------
the command line: nothing dangerous is on by default
PASS  --apply is off by default, so a plain run changes nothing  <-- pinned defect
PASS  and no host is probed by default, so a plain run sends no packet  <-- pinned defect
PASS  a unique prefix of --apply is refused, so a short flag cannot arm the fix path  <-- pinned defect
PASS  there is no password option at all: nothing here signs in to anything, and a connection file is never opened
PASS  --self-test wins over every other flag, so a test run can neither apply a fix, nor probe a host, nor write a file  <-- pinned defect
...
----------------------------------------------------------------------
the reading layer, against a real temporary tree and a real socket
PASS  a depth of one stops at the first level, because a full walk of a synced profile can itself hydrate every file it touches
PASS  renaming a folder aside moves it and leaves nothing behind, which is what the cache fix does instead of deleting
PASS  a listening port is reported open
PASS  a port with nothing behind it is reported closed
PASS  and the probe returns inside its own timeout. Not faster than it: Linux refuses a dead loopback port at once, Windows retransmits and times out, and the connect this replaced blocked for tens of seconds against a dead host  <-- pinned defect
PASS  memory answers both numbers or neither, so no check can compute a verdict from half a reading  <-- pinned defect
----------------------------------------------------------------------
the tool end to end on the machine running this, read-only
PASS  a real run exits 0, 1 or 2, whatever this machine turns out to be
PASS  a plain run applies nothing to the machine it is run on  <-- pinned defect
PASS  and not one record of a real run pairs a verdict with text saying it measured nothing  <-- pinned defect
PASS  --report writes exactly two files, and creates the directory
----------------------------------------------------------------------
the harness records a failure as a failure
PASS  a false check, a missing exception, a wrong exception and an accepted argument list are four failures, so a broken tool turns this self-test red  <-- pinned defect
PASS  not one of those four counted as a pass
PASS  and every one of them printed a line the operator can see
----------------------------------------------------------------------
393 assertions, 0 failed
```

## Requirements

Python 3.9 or newer. Standard library only: `argparse`, `collections`, `json`, `ntpath`, `os`,
`re`, `socket`, `sys`, `time`, plus `winreg`, `ctypes`, `subprocess` and `shutil` imported inside
the functions that need them, and `xml.etree`, `io`, `tempfile` for the parser and the self-test.
It runs on ArcGIS Pro's Python and on a plain `python3`. `arcpy` is not used and the `arcgis`
package is not needed.

```
git clone https://github.com/uhsear/prostall.git
python prostall.py --self-test
```

`--self-test` needs no registry, no socket, no disk and no ArcGIS install, so you can check the
tool before you point it at somebody's workstation. It drives every check through a stand-in
machine that answers inside the process: a healthy one, a sick one, one that reads back nothing,
one whose registry provider dies mid-run, and one logged in under the wrong profile. It also
exercises the reading layer itself against a real temporary directory and a real loopback socket,
and runs the whole tool once, read-only, on the machine you run it on.

The same 393 assertions pass on Windows and on Linux. That matters more than it sounds: the path
logic answers questions about Windows paths, and two of the bugs it pins are cases where the
standard library answers for the host instead of for the path.

## Quick start

Run it in the editor's own session, without elevation, while Pro is closed.

```
python prostall.py
```

That reads the machine and prints the report. Nothing is written, no host is contacted, and no
setting is changed.

```
python prostall.py --sde-server gisdb01 --portal gis.example.org --report C:\Temp\properf
```

That adds two bounded TCP probes and writes the report as text and as JSON.

## Usage

| Flag | Default | What it does |
|---|---|---|
| `--self-test` | off | Run the offline assertions and exit. Wins over every other flag. |
| `--verbose` | off | Print the expected text and the evidence lines as well. |
| `--json` | off | Print the report as JSON on stdout instead of the console form. |
| `--report DIR` | none | Write the text and JSON reports into this directory. Without it nothing is written. |
| `--sde-server HOST` | none | TCP-probe this geodatabase host. Connect only, no credential. Without it the probe is skipped. |
| `--sde-port PORT` | `1433` | Port for that probe. |
| `--portal HOST` | none | TCP-probe this portal host on 443. Without it the probe is skipped. |
| `--timeout MS` | `4000` | Bound on each network probe. |
| `--apply` | off | Run the gated fixes. Each is refused unless its check actually failed, prints its own undo, and never deletes anything. |

There is no password option and no connection string. Nothing here signs in to anything, and a
`.sde` connection file is recorded by path and never opened, because those files can carry a saved
credential.

## What it checks

Twenty-two checks. The eleven that bear on lost edits run first and print first, because silent
edit loss outranks every performance finding.

**Data loss**, in the order they run and print.

| Id | What it measures |
|---|---|
| DL-00 | Whether the tool is running as the account that actually edits. If another profile carries the Pro data, every per-user result below is invalid. |
| DL-05 | Where the recently opened projects live: local disk, a share, or a synced folder. |
| DL-03 | The project backup interval, and that it is not an edit autosave. It copies the project file, never the edit session. |
| DL-06 | Whether Documents is redirected into OneDrive by Known Folder Move. |
| DL-07 | Dehydrated Files-On-Demand placeholders anywhere under the project tree. |
| DL-08 | The Offline Files cache, read from the policy value and from nowhere else. |
| DL-09 | Crash dumps, and what dump collection is configured if there are none. |
| DL-10 | A bounded TCP connect to the geodatabase host, with its latency. |
| DL-11 | Connection files on the box, by path, including the copies cached under the search index. |
| DL-12 | Whether Pro is running right now, which blocks the cache fix. |
| PF-07 | Leftover session folders, and which of them still hold a project file or a scratch table with rows in it. |

**Performance**

| Id | What it measures |
|---|---|
| PF-04 | The installed release and build. |
| PF-05 | The display settings, read only. |
| PF-06 | The local cache: size, and how much of it is orphaned. |
| PF-08 | The catalog search index, and whether it indexes network connections. |
| PF-11 | Which graphics adapter Windows hands Pro. |
| PF-12 | Installed and free memory. |
| PF-13 | Free space on the system volume and on any local project volume. |
| PF-15 | The active power plan. |
| PF-19 | A bounded TCP connect to the portal. |
| PF-26 | Whether a roaming profile carries the ESRI settings folder. |
| PF-27 | Symbology that does not refresh after a field calculation. |

PF-07 keeps its performance id and runs in the data-loss block on purpose. An earlier version
reported those folders as a count and a size and called it disk churn, which routed a possible
recovery lead for the lost work into the performance section and out of the act-first list.

Three checks were deleted rather than rewritten. Two read a geodatabase the workstation cannot see,
and the third read an attribute rule definition that lives on the server. All three printed
findings a workstation had no way to produce.

## The five statuses

| Status | Means |
|---|---|
| `Pass` | Measured, and it is what it should be. |
| `Warn` | Measured, and it is a contributing cause. |
| `Fail` | Measured, and it is a cause. |
| `Info` | Read, and it decides nothing. |
| `Skipped` | Not read at all. The probe threw, produced nothing, or was never asked to run. |

`Pass`, `Warn` and `Fail` are verdicts. `Info` and `Skipped` are not, and the difference is
enforced rather than documented:

- The record constructor refuses a verdict on a check whose evidence text says it did not measure,
  and refuses one on a check that declares itself unmeasured.
- A check body that throws is recorded `Skipped`, never `Warn`. Every fix gates on `Warn` or
  `Fail`, so `Warn` would let a fix fire on a determination nobody made.
- A check body that records nothing at all is recorded `Skipped` too, because saying nothing reads
  as saying `Pass`.
- The act-first list is exactly the data-loss checks in `Warn` or `Fail`, computed from the
  records. It carries no list of ids. The version this replaced kept two ids in the roll-up so they
  stayed listed "even if a future branch demotes them", which is a report promoting a finding the
  check itself had withdrawn.

## Exit codes

| Code | Means |
|---|---|
| 0 | Nothing to act on. |
| 1 | Performance findings, none of them bearing on lost edits. |
| 2 | At least one finding bearing on lost edits. |
| 64 | Usage error. |

A run made entirely of `Info` and `Skipped` exits 0. Undetermined is not a finding, and the summary
prints the skipped count on its own line so nobody reads that 0 as a clean bill of health.

## The fixes

`--apply` runs two fixes, and only two. Both are per-user, both are gated, and both print the
command that undoes them.

| Id | Acts on | What it does |
|---|---|---|
| AP-01 | PF-06 | Renames the local cache folder aside so Pro rebuilds it. Refused while Pro is running. |
| AP-02 | PF-11 | Writes the high-performance graphics preference for ArcGIS Pro. |

Four gates, in order: the check must exist, it must not be `Skipped`, it must be in `Warn` or
`Fail`, and a per-user fix is refused when the session check failed. That last one matters on a
remoted-in support session, where the per-user fix would write into the support account's hive and
report success while changing nothing for the editor.

AP-01 renames. It does not delete. A diagnostic that deletes a folder is how the last copy of
something disappears, and the undo is a single `move` back.

Nothing else is automated, on purpose. OneDrive redirection, the project location, the power plan,
Defender, dump collection and anything inside a geodatabase are reported and never touched. Those
are policy decisions or reviewed operator actions, and a script that makes them for you is a script
nobody will run twice.

## Output

The console report lists the data-loss block, then the performance block, then a tally, then the
findings to act on first. `--report` writes the same thing as text, plus a JSON document beside it:

```json
{
 "prostall": 1,
 "taken": "2026-09-17 20:59",
 "user": "editor",
 "elevated": false,
 "act_first": ["DL-05", "DL-03", "DL-06"],
 "fixable": ["PF-06"],
 "counts": {"Fail": 2, "Warn": 3, "Pass": 7, "Info": 8, "Skipped": 2},
 "applied": [],
 "notes": ["would apply [AP-01] Rename the ESRI local cache folder aside so Pro rebuilds it.",
           "skip [AP-02] PF-11 is already healthy (Pass)"],
 "checks": [{"id": "DL-06", "category": "Storage", "status": "Fail", "dataloss": true,
             "title": "Documents redirected into OneDrive (Known Folder Move)",
             "observed": "...", "expected": "...", "impact": "...", "fix": "...",
             "autofixable": false, "detail": ""}]
}
```

Diff that JSON against a workstation that is known to be fast. That is the fastest way to find what
is different about this one, and it is why every timestamp in the report is UTC: two machines in
different time zones would otherwise disagree on every dated line.

A check-only run still evaluates the fix gates and prints what it would have done. `applied` is
empty unless `--apply` was given, and the self-test asserts that across a whole run.

## Limits

- It reads a workstation. It does not read a server. Nothing here opens a geodatabase, runs a
  query, or signs in to a portal, and the two network probes are TCP connects that send nothing.
- Off Windows almost every check reports `Info` or `Skipped`. That is correct behaviour and not a
  port: an unreadable registry is not an absent value, and the tool says so rather than guessing.
- Several readings need Pro's own configuration. Run it in the editor's session. DL-00 exists to
  tell you when you did not.
- The OneDrive redirection bitmask is printed and deliberately not decoded. The value most guides
  name does not exist on current builds, and on a machine whose folders were all redirected it
  rendered as absent, so the line contradicted the finding. The verdict comes from the Documents
  path, which is measured directly.
- No event log, no WMI, no scheduled tasks. Those need either a heavier dependency or an elevated
  session, and every reading here is meant to work from the editor's own unelevated session.
- It finds recently opened projects by looking under the Documents project folder. A project kept
  somewhere else is not in that list, and DL-05 says what it looked at rather than claiming
  coverage.
- It does not diagnose a network. `DL-10` says the host answered in so many milliseconds. Why it
  was slow is somebody else's tool.

## Related

Other single-file tools in this portfolio that pair with this one:

- [cimscan](https://github.com/uhsear/cimscan) - once the workstation is ruled out, report what the project actually points at, and refuse to call an unreadable project a clean one
- [gdbxray](https://github.com/uhsear/gdbxray) - read the geodatabase schema behind the layers the slow project draws
- [gdbfence](https://github.com/uhsear/gdbfence) - keep a File Geodatabase out of the places this tool finds them in

## Contributing

Open an issue or pull request on GitHub.

## Author

Built by [Asir Khan](https://www.linkedin.com/in/asir-khan-310317264/).

## License

MIT.
