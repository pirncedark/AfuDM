package com.afudm.afutube

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertNotNull

class ShareIntentViewModelTest {
    @Test
    fun `extracts first URL from titled share text`() {
        val payload = ShareIntentPayload(
            action = "android.intent.action.SEND",
            text = "Başlık https://youtu.be/Wz4qYO-91zg?si=abc ve https://example.com/ikinci"
        )

        assertEquals(
            "https://youtu.be/Wz4qYO-91zg?si=abc",
            ShareUrlExtractor.firstHttpUrl(payload)
        )
    }

    @Test
    fun `uses ACTION_VIEW data URI`() {
        val payload = ShareIntentPayload(
            action = "android.intent.action.VIEW",
            data = "https://www.youtube.com/shorts/abc123"
        )

        assertEquals(
            "https://www.youtube.com/shorts/abc123",
            ShareUrlExtractor.firstHttpUrl(payload)
        )
    }

    @Test
    fun `url-less text produces no event`() {
        val viewModel = ShareIntentViewModel()

        viewModel.publish(ShareIntentPayload(action = "android.intent.action.SEND", text = "Sadece başlık"))

        assertNull(viewModel.events.value)
    }

    @Test
    fun `same URL published twice creates two events`() {
        val viewModel = ShareIntentViewModel()
        val payload = ShareIntentPayload(action = "android.intent.action.SEND", text = "https://youtu.be/abc")

        viewModel.publish(payload)
        val first = viewModel.events.value
        viewModel.publish(payload)
        val second = viewModel.events.value

        assertNotNull(first)
        assertNotNull(second)
        assertEquals(first!!.url, second!!.url)
        assertEquals(first.sequence + 1, second.sequence)
    }

    @Test
    fun `same sequence is consumed only once`() {
        val viewModel = ShareIntentViewModel()
        viewModel.publish(ShareIntentPayload(text = "https://example.com/video"))
        val event = viewModel.events.value!!

        assertEquals(event, viewModel.consume(event.sequence))
        assertNull(viewModel.consume(event.sequence))
    }

    @Test
    fun `new share gets a new sequence and can be consumed`() {
        val viewModel = ShareIntentViewModel()
        viewModel.publish(ShareIntentPayload(text = "https://example.com/one"))
        val first = viewModel.events.value!!
        viewModel.consume(first.sequence)

        viewModel.publish(ShareIntentPayload(text = "https://example.com/two"))
        val second = viewModel.events.value!!

        assertEquals(first.sequence + 1, second.sequence)
        assertEquals("https://example.com/two", viewModel.consume(second.sequence)?.url)
    }
}
