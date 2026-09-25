"use client";

import {
  useEffect,
  useEffectEvent,
  useLayoutEffect,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { CrashScreen } from "./CrashScreen";
import { getNode, type RepoCta, type RepoEdition, type RepoFileNode, type RepoFolderNode } from "./model";
import {
  BLANK,
  CONFIRM_PLACEHOLDER,
  CONFIRM_PROMPT,
  PLOP_PROMPT,
  RM_ABORTED,
  RM_CRASH_AT,
  RM_STEPS,
  completeInput,
  isConfirmed,
  plopPlan,
  promptFor,
  rootPrompt,
  runCommand,
  type Cwd,
  type TimelineStep,
} from "./terminal-engine";

export interface RepoTerminalProps {
  /** Root name + repo stats (git chart). */
  edition: RepoEdition;
  /** Current tree (includes files added by plop). */
  tree: RepoFolderNode;
  /** Pinned "get-access" line. */
  cta: RepoCta;
  /** Input placeholder before the first command (CA "try: git, ls, tree, plop, cat README.md"). */
  placeholder: string;
  /** Header label ("Terminal"). */
  title: string;
  /** Run `command` whenever `id` changes (footer commits button → "git"). */
  request?: { id: number; command: string };
  onOpenFile: (path: string) => void;
  onAddFile: (folderPath: string, file: RepoFileNode) => void;
}

interface Entry {
  id: number;
  /** Prompt shown on the echo line (as it was when the command ran). */
  prompt: string;
  input: string;
  lines: string[];
  /** Text of the spinner line while a timed sequence works, else null. */
  spinner: string | null;
}

/** idle: shell prompt · plop: plop's name question · confirm: rm's y/N · running: timed output. */
type Phase = "idle" | "plop" | "confirm" | "running";

export function RepoTerminal(props: RepoTerminalProps) {
  const { edition, tree, cta, placeholder, title, request } = props;

  const [entries, setEntries] = useState<Entry[]>([]);
  const [cwd, setCwd] = useState<Cwd>("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [history, setHistory] = useState<string[]>([]);
  const [value, setValue] = useState("");
  const [crashed, setCrashed] = useState(false);

  const bodyRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const nextIdRef = useRef(0);
  /** Position while walking the history with the arrow keys (null = not browsing). */
  const historyIndexRef = useRef<number | null>(null);
  /** Refocus the input when a timed sequence ends (it had focus when it started). */
  const refocusRef = useRef(false);
  const handledRequestRef = useRef<number | undefined>(undefined);
  const timeoutsRef = useRef<Set<number>>(new Set());
  /** Latest callbacks, for timeouts that fire after later renders. */
  const callbacksRef = useRef({ onOpenFile: props.onOpenFile, onAddFile: props.onAddFile });

  useEffect(() => {
    callbacksRef.current = { onOpenFile: props.onOpenFile, onAddFile: props.onAddFile };
  });

  useEffect(() => {
    const timeouts = timeoutsRef.current;
    return () => {
      timeouts.forEach((id) => window.clearTimeout(id));
      timeouts.clear();
    };
  }, []);

  // Keep the newest output in view.
  useLayoutEffect(() => {
    const body = bodyRef.current;
    if (body) body.scrollTop = body.scrollHeight;
  }, [entries, phase]);

  // The form is hidden while a sequence runs: give focus back once it returns.
  useEffect(() => {
    if (phase === "running" || !refocusRef.current) return;
    refocusRef.current = false;
    inputRef.current?.focus({ preventScroll: true });
  }, [phase]);

  const rootName = edition.tree.name;
  const pinnedPrompt = rootPrompt(rootName);
  const currentPrompt = phase === "plop" ? PLOP_PROMPT : phase === "confirm" ? CONFIRM_PROMPT : promptFor(rootName, cwd);

  const schedule = (ms: number, fn: () => void) => {
    const id = window.setTimeout(() => {
      timeoutsRef.current.delete(id);
      fn();
    }, ms);
    timeoutsRef.current.add(id);
  };

  const pushEntry = (entry: Omit<Entry, "id">) => {
    const id = ++nextIdRef.current;
    setEntries((prev) => [...prev, { id, ...entry }]);
    return id;
  };

  const updateEntry = (id: number, update: (entry: Entry) => Entry) => {
    setEntries((prev) => prev.map((entry) => (entry.id === id ? update(entry) : entry)));
  };

  /** Play `steps` into entry `id`, then call `onDone` at `doneAt`. */
  const playTimeline = (id: number, steps: TimelineStep[], doneAt: number, onDone: () => void) => {
    refocusRef.current = document.activeElement === inputRef.current;
    setPhase("running");
    for (const step of steps) {
      schedule(step.at, () =>
        updateEntry(id, (entry) => ({
          ...entry,
          lines: step.line === undefined ? entry.lines : [...entry.lines, step.line],
          spinner: step.spinner === undefined ? entry.spinner : step.spinner,
        })),
      );
    }
    schedule(doneAt, onDone);
  };

  const answerPlop = (name: string) => {
    const plan = plopPlan(name, tree);
    const folderExists = getNode(tree, plan.folderPath)?.type === "folder";
    const id = pushEntry({ prompt: PLOP_PROMPT, input: name, lines: plan.lines, spinner: plan.spinner });
    playTimeline(id, plan.steps, plan.doneAt, () => {
      const { onAddFile, onOpenFile } = callbacksRef.current;
      onAddFile(plan.folderPath, plan.file);
      if (folderExists) onOpenFile(plan.openPath);
      setPhase("idle");
    });
  };

  const answerConfirm = (answer: string) => {
    if (!isConfirmed(answer)) {
      pushEntry({ prompt: CONFIRM_PROMPT, input: answer, lines: [RM_ABORTED], spinner: null });
      setPhase("idle");
      return;
    }
    const id = pushEntry({ prompt: CONFIRM_PROMPT, input: answer, lines: [], spinner: null });
    playTimeline(id, RM_STEPS, RM_CRASH_AT, () => setCrashed(true));
  };

  const runShell = (input: string) => {
    const result = runCommand(input, { tree, repo: edition.repo, cwd, history });
    if (input) setHistory((prev) => [...prev, input]);
    if (result.clear) setEntries([]);
    else pushEntry({ prompt: promptFor(rootName, cwd), input, lines: result.lines, spinner: null });
    if (result.cwd !== undefined) setCwd(result.cwd);
    if (result.openPath !== undefined) props.onOpenFile(result.openPath);
    if (result.next === "plop") setPhase("plop");
    else if (result.next === "confirm") setPhase("confirm");
  };

  const submit = (raw: string, fromPhase: Phase = phase) => {
    const input = raw.trim();
    historyIndexRef.current = null;
    if (fromPhase === "running") return;
    if (fromPhase === "plop") answerPlop(input);
    else if (fromPhase === "confirm") answerConfirm(input);
    else runShell(input);
  };

  // Footer "commits" button: run the requested command as if typed (a pending prompt is dropped).
  const runRequest = useEffectEvent(() => {
    if (!request || phase === "running") return;
    if (phase !== "idle") setPhase("idle");
    submit(request.command, "idle");
  });

  const requestId = request?.id;
  useEffect(() => {
    if (requestId === undefined || handledRequestRef.current === requestId) return;
    handledRequestRef.current = requestId;
    runRequest();
  }, [requestId]);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    submit(value);
    setValue("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Tab") {
      event.preventDefault();
      if (phase !== "idle") return;
      const completed = completeInput(value, cwd, tree);
      if (completed !== null) setValue(completed);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (history.length === 0) return;
      const index = historyIndexRef.current === null ? history.length - 1 : Math.max(0, historyIndexRef.current - 1);
      historyIndexRef.current = index;
      setValue(history[index]);
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      const index = historyIndexRef.current;
      if (index === null) return;
      if (index >= history.length - 1) {
        historyIndexRef.current = null;
        setValue("");
      } else {
        historyIndexRef.current = index + 1;
        setValue(history[index + 1]);
      }
    }
  };

  const focusInput = () => {
    if (window.getSelection()?.toString()) return;
    inputRef.current?.focus({ preventScroll: true });
  };

  const inputPlaceholder =
    phase === "idle" && entries.length === 0 ? placeholder : phase === "confirm" ? CONFIRM_PLACEHOLDER : undefined;

  return (
    <section aria-label="Terminal" className="flex h-full min-h-0 flex-col">
      <div className="shrink-0 border-white/10 border-b px-16 py-8 font-mono text-caption-10 text-white/40 uppercase tracking-wide">
        {title}
      </div>
      <div
        ref={bodyRef}
        className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-16 py-10 font-mono text-caption-10 leading-relaxed"
        data-lenis-prevent
        onClick={focusInput}
      >
        {entries.map((entry) => (
          <div key={entry.id} className="whitespace-pre-wrap break-words">
            <div className="text-white/80">
              <span className="select-none text-white/40">{entry.prompt} </span>
              {entry.input}
            </div>
            {entry.lines.map((line, i) => (
              <div key={i} className="text-white/50">
                {line === "" ? BLANK : line}
              </div>
            ))}
            {entry.spinner !== null && (
              <div className="flex items-center gap-8 text-white/50">
                <span
                  aria-hidden="true"
                  className="size-12 shrink-0 animate-spin rounded-full border border-white/20 border-t-white/70 motion-reduce:animate-none"
                />
                <span>{entry.spinner}</span>
              </div>
            )}
          </div>
        ))}
        <a
          aria-label={`${cta.label}: get access`}
          className="group block whitespace-pre-wrap break-words text-white/80 no-underline"
          href={cta.href}
        >
          <span className="select-none text-white/40">{pinnedPrompt} </span>
          <span className="text-[#d6a878] group-hover:underline">{cta.label}</span>
          <span className="select-none text-white/40">{`   # ${cta.note}`}</span>
        </a>
        {phase !== "running" && (
          <form className="flex items-center text-white/80" onSubmit={onSubmit}>
            <span className="select-none text-white/40">{`${currentPrompt} `}</span>
            <input
              ref={inputRef}
              type="text"
              aria-label="Terminal input"
              spellCheck={false}
              autoCapitalize="off"
              autoCorrect="off"
              autoComplete="off"
              placeholder={inputPlaceholder}
              value={value}
              onChange={(event) => setValue(event.target.value)}
              onKeyDown={onKeyDown}
              className="min-w-0 flex-1 bg-transparent font-mono text-caption-10 caret-current outline-none ring-0 placeholder:text-white/25 focus:outline-none focus:ring-0 focus-visible:outline-none focus-visible:ring-0"
            />
          </form>
        )}
      </div>
      {crashed && <CrashScreen />}
    </section>
  );
}
