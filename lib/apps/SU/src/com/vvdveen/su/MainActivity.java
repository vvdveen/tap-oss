package com.vvdveen.su;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;

import android.os.Bundle;
import android.app.Activity;
import android.util.Log;
import android.view.Menu;

public class MainActivity extends Activity {

	private static String TAG = "com.vvdveen.su";

	@Override
	protected void onCreate(Bundle savedInstanceState) {
		super.onCreate(savedInstanceState);
		setContentView(R.layout.activity_main);
		
		Process proc;
		
		try {
    		proc = Runtime.getRuntime().exec("su -c 'id'");
    	
    		BufferedReader stdInput = new BufferedReader(new InputStreamReader(proc.getInputStream()));
    		BufferedReader stdError = new BufferedReader(new InputStreamReader(proc.getErrorStream()));
    		String s;
    	
    		Log.d(TAG, "stdout:");
    		while ((s = stdInput.readLine())  != null) {
	    		Log.d(TAG, s);
    		}
    		Log.d(TAG, "stderr:");
    		while ((s = stdError.readLine()) != null) {
	    		Log.d(TAG, s);
    		}
    		Log.d(TAG, "finished");
    	} catch (IOException e) {
    	}
	}

	@Override
	public boolean onCreateOptionsMenu(Menu menu) {
		// Inflate the menu; this adds items to the action bar if it is present.
		getMenuInflater().inflate(R.menu.main, menu);
		return true;
	}

}
