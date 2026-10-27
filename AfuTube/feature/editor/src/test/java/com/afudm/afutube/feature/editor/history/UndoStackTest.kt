package com.afudm.afutube.feature.editor.history

import org.junit.Assert.*
import org.junit.Test

class UndoStackTest {
    @Test fun supportsAtLeastThirtyUndoRedoSteps() {
        var value = 0
        val history = UndoStack()
        repeat(35) { history.execute(object : EditorCommand { override fun execute() { value++ }; override fun undo() { value-- } }) }
        repeat(35) { assertTrue(history.undo()) }
        assertEquals(0, value)
        repeat(35) { assertTrue(history.redo()) }
        assertEquals(35, value)
    }
    @Test fun newCommandAfterUndoDropsRedoBranch() {
        var value = 0; val history = UndoStack()
        fun increment() = object : EditorCommand { override fun execute() { value++ }; override fun undo() { value-- } }
        history.execute(increment()); history.undo(); history.execute(increment())
        assertFalse(history.canRedo); assertEquals(1, value)
    }
    @Test fun capacityKeepsNewestUndoCommands() {
        var value = 0; val history = UndoStack(30)
        repeat(31) { history.execute(object : EditorCommand { override fun execute() { value++ }; override fun undo() { value-- } }) }
        repeat(30) { assertTrue(history.undo()) }
        assertEquals(1, value); assertFalse(history.canUndo)
    }
}
