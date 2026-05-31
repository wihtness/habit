package com.example.habit

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity
import com.example.habit.databinding.ActivityMainBinding

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        binding.ctaButton.setOnClickListener {
            binding.statusText.text = getString(R.string.status_after_click)
        }
    }
}

