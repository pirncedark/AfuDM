package com.afudm.afutube.feature.editor.history

/** A reversible operation. Execute and undo must both be safe to call only once per history move. */
interface EditorCommand {
    fun execute()
    fun undo()
}

/** Bounded command history. A new command clears redo history and oldest undo entries are discarded. */
class UndoStack(private val capacity: Int = 100) {
    init { require(capacity > 0) }
    private val undoCommands = ArrayDeque<EditorCommand>()
    private val redoCommands = ArrayDeque<EditorCommand>()
    val canUndo get() = undoCommands.isNotEmpty()
    val canRedo get() = redoCommands.isNotEmpty()
    val undoCount get() = undoCommands.size
    val redoCount get() = redoCommands.size

    fun execute(command: EditorCommand) {
        command.execute()
        undoCommands.addLast(command)
        while (undoCommands.size > capacity) undoCommands.removeFirst()
        redoCommands.clear()
    }
    fun undo(): Boolean {
        val command = undoCommands.removeLastOrNull() ?: return false
        command.undo(); redoCommands.addLast(command); return true
    }
    fun redo(): Boolean {
        val command = redoCommands.removeLastOrNull() ?: return false
        command.execute(); undoCommands.addLast(command); return true
    }
    fun clear() { undoCommands.clear(); redoCommands.clear() }
}

/** Adapts an immutable project transformation to the command history. */
class ProjectEditCommand<T>(private val read: () -> T, private val write: (T) -> Unit, private val transform: (T) -> T) : EditorCommand {
    private var before: T? = null
    private var after: T? = null
    private var captured = false
    override fun execute() {
        if (!captured) { val current = read(); before = current; after = transform(current); captured = true }
        @Suppress("UNCHECKED_CAST") write(after as T)
    }
    override fun undo() {
        check(captured) { "Command must execute before undo" }
        @Suppress("UNCHECKED_CAST") write(before as T)
    }
}
