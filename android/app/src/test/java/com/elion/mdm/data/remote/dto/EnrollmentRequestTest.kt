package com.elion.mdm.data.remote.dto

import com.google.gson.Gson
import com.google.gson.JsonParser
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Test

class EnrollmentRequestTest {

    @Test
    fun serializesBootstrapTokenFromCaller() {
        val tokenFromUi = "5bce0e2b-b35b-49e2-b35e-b988065f195f"
        val request = EnrollmentRequest(
            deviceId = "android-id-1",
            name = "Pixel 8",
            deviceType = "android",
            bootstrapToken = tokenFromUi,
            extraData = null
        )

        val json = JsonParser.parseString(Gson().toJson(request)).asJsonObject

        assertEquals(tokenFromUi, json["bootstrap_token"].asString)
        assertFalse(json.has("bootstrap_secret"))
        assertFalse(json.has("bootstrapSecret"))
    }
}
