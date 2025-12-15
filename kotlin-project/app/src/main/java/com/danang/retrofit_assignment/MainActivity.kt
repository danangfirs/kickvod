package com.danang.retrofit_assignment

import android.content.DialogInterface
import android.os.Bundle
import android.view.LayoutInflater
import android.widget.EditText
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.recyclerview.widget.LinearLayoutManager
import com.danang.retrofit_assignment.databinding.ActivityMainBinding
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response

class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var adapter: PostAdapter
    private val postsList = mutableListOf<Post>()

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        setupRecyclerView()
        setupListeners()
        fetchPosts()
    }

    private fun setupRecyclerView() {
        adapter = PostAdapter(postsList)
        binding.recyclerView.layoutManager = LinearLayoutManager(this)
        binding.recyclerView.adapter = adapter
    }

    private fun setupListeners() {
        binding.swipeRefreshLayout.setOnRefreshListener {
            fetchPosts()
        }

        binding.fabAdd.setOnClickListener {
            showAddPostDialog()
        }
    }

    private fun fetchPosts() {
        binding.progressBar.visibility = android.view.View.VISIBLE
        RetrofitClient.instance.getPosts().enqueue(object : Callback<List<Post>> {
            override fun onResponse(call: Call<List<Post>>, response: Response<List<Post>>) {
                binding.progressBar.visibility = android.view.View.GONE
                binding.swipeRefreshLayout.isRefreshing = false
                if (response.isSuccessful) {
                    response.body()?.let {
                        adapter.updateData(it)
                    }
                } else {
                    showError("Failed to load posts: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<List<Post>>, t: Throwable) {
                binding.progressBar.visibility = android.view.View.GONE
                binding.swipeRefreshLayout.isRefreshing = false
                showError("Network error: ${t.message}")
            }
        })
    }

    private fun showAddPostDialog() {
        val dialogView = LayoutInflater.from(this).inflate(R.layout.dialog_add_post, null)
        val etUserId = dialogView.findViewById<EditText>(R.id.etUserId)
        val etTitle = dialogView.findViewById<EditText>(R.id.etTitle)
        val etBody = dialogView.findViewById<EditText>(R.id.etBody)

        AlertDialog.Builder(this)
            .setView(dialogView)
            .setPositiveButton("Post") { _, _ ->
                val userIdStr = etUserId.text.toString()
                val title = etTitle.text.toString()
                val body = etBody.text.toString()

                if (userIdStr.isNotEmpty() && title.isNotEmpty() && body.isNotEmpty()) {
                    val userId = userIdStr.toIntOrNull()
                    if (userId != null) {
                        createPost(Post(userId = userId, title = title, body = body))
                    } else {
                        showError("Invalid User ID")
                    }
                } else {
                    showError("Please fill all fields")
                }
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    private fun createPost(post: Post) {
        binding.progressBar.visibility = android.view.View.VISIBLE
        RetrofitClient.instance.createPost(post).enqueue(object : Callback<Post> {
            override fun onResponse(call: Call<Post>, response: Response<Post>) {
                binding.progressBar.visibility = android.view.View.GONE
                if (response.isSuccessful) {
                    Toast.makeText(this@MainActivity, "Post Created! Status: ${response.code()}", Toast.LENGTH_LONG).show()
                    // Instead of fetching all posts, add the new post to the adapter directly
                    response.body()?.let {
                        adapter.addPost(it)
                        binding.recyclerView.scrollToPosition(0) // Scroll to the top to see the new post
                    }
                } else {
                    showError("Failed to create post: ${response.code()}")
                }
            }

            override fun onFailure(call: Call<Post>, t: Throwable) {
                binding.progressBar.visibility = android.view.View.GONE
                showError("Network error: ${t.message}")
            }
        })
    }

    private fun showError(message: String) {
        Toast.makeText(this, message, Toast.LENGTH_SHORT).show()
    }
}
