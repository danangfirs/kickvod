package com.danang.retrofit_assignment

import com.google.gson.annotations.SerializedName

data class Post(
    @SerializedName("userId") val userId: Int,
    @SerializedName("id") val id: Int? = null,
    @SerializedName("title") val title: String,
    @SerializedName("body") val body: String
)
