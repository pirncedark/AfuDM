package com.afudm.afutube.core.extractor

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class InstagramCookiesTest {
    @Test
    fun `empty cookie header produces only file header`() {
        assertEquals("# Netscape HTTP Cookie File\n", InstagramCookies.toNetscape(""))
    }

    @Test
    fun `converts cookies preserving equals in values`() {
        assertEquals(
            "# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t0\tsessionid\ttest==\n" +
                ".instagram.com\tTRUE\t/\tTRUE\t0\tcsrftoken\tvalue\n",
            InstagramCookies.toNetscape("sessionid=test==; csrftoken=value")
        )
    }

    @Test
    fun `ignores malformed cookies and line injection`() {
        assertEquals(
            "# Netscape HTTP Cookie File\n.instagram.com\tTRUE\t/\tTRUE\t0\tvalid\t\n",
            InstagramCookies.toNetscape("broken; =bad; injected=x\nline; tab=x\ty; valid=")
        )
    }

    @Test
    fun `matches only Instagram hosts`() {
        assertTrue(InstagramCookies.isInstagram("https://www.instagram.com/stories/highlights/123/"))
        assertTrue(InstagramCookies.isInstagram("https://instagram.com/"))
        assertFalse(InstagramCookies.isInstagram("https://instagram.com.evil.example/"))
        assertFalse(InstagramCookies.isInstagram("https://evil.example/instagram.com"))
        assertFalse(InstagramCookies.isInstagram("invalid"))
        assertFalse(InstagramCookies.isInstagram("ftp://instagram.com/"))
    }

    @Test
    fun `extracts numeric story pk from decoded query`() {
        assertEquals("4002849496279096279", InstagramCookies.storyMediaPk(
            "https://instagram.com/stories/highlights/123/?story_media_id=4002849496279096279%5F1581116288"
        ))
        assertEquals("123", InstagramCookies.storyMediaPk("https://instagram.com/?story_media_id=123"))
        assertNull(InstagramCookies.storyMediaPk("https://instagram.com/"))
        assertNull(InstagramCookies.storyMediaPk("https://instagram.com/?story_media_id=bad_123"))
        assertNull(InstagramCookies.storyMediaPk("https://instagram.com/?story_media_id=%"))
    }

    @Test
    fun `story code matches yt-dlp entry id`() {
        assertEquals("DeM-mirERvX", InstagramCookies.storyMediaCode(
            "https://www.instagram.com/stories/highlights/18072912233468488/?story_media_id=4002849496279096279_1581116288"
        ))
        assertNull(InstagramCookies.storyMediaCode("https://instagram.com/"))
    }
}
