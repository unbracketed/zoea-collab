/**
 * Register Component
 *
 * Registration form using shadcn/ui components for creating new user accounts.
 * Matches the existing Login component design.
 */

import { useState } from 'react';
import { Loader2 } from 'lucide-react';
import api from '../services/api';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

function Register({ onSwitchToLogin, onRegistrationSuccess }) {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password1: '',
    password2: '',
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [registeredEmail, setRegisteredEmail] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear error when user types
    if (error) setError('');
  };

  const validateForm = () => {
    // Client-side validation
    if (!formData.username || !formData.email || !formData.password1 || !formData.password2) {
      setError('All fields are required');
      return false;
    }

    if (formData.username.length < 3) {
      setError('Username must be at least 3 characters long');
      return false;
    }

    if (formData.password1.length < 8) {
      setError('Password must be at least 8 characters long');
      return false;
    }

    if (formData.password1 !== formData.password2) {
      setError('Passwords do not match');
      return false;
    }

    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(formData.email)) {
      setError('Please enter a valid email address');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    if (!validateForm()) {
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await api.signup(formData);

      if (response.success) {
        setSuccess(true);
        setRegisteredEmail(formData.email);

        // Call success callback if provided
        if (onRegistrationSuccess) {
          onRegistrationSuccess({
            email: formData.email,
            username: formData.username,
          });
        }
      }
    } catch (err) {
      console.error('Registration error:', err);
      setError(err.message || 'Registration failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleResendVerification = async () => {
    setIsSubmitting(true);
    setError('');

    try {
      const response = await api.resendVerification(registeredEmail);
      if (response.success) {
        setError(''); // Clear any errors
        // Show success message in error field (as info)
        setError('Verification email sent! Please check your inbox.');
      }
    } catch (err) {
      console.error('Resend verification error:', err);
      setError(err.message || 'Failed to resend verification email. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Success state - show verification instructions
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center p-4">
        <div className="w-full max-w-md">
          <Card>
            <CardHeader className="text-center">
              <CardTitle className="text-2xl">Check Your Email</CardTitle>
              <CardDescription>Registration successful!</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col gap-6">
                <div className="bg-primary/10 border border-primary text-primary-foreground px-4 py-3 rounded-md text-sm">
                  <p className="font-medium mb-2">Welcome to Zoea Studio!</p>
                  <p>
                    We've sent a verification email to <strong>{registeredEmail}</strong>.
                    Please check your inbox and click the verification link to activate your account.
                  </p>
                </div>

                {error && (
                  <div className="bg-muted border border-border px-4 py-3 rounded-md text-sm">
                    {error}
                  </div>
                )}

                <div className="flex flex-col gap-3">
                  <Button
                    onClick={handleResendVerification}
                    variant="outline"
                    className="w-full"
                    disabled={isSubmitting}
                  >
                    {isSubmitting ? (
                      <>
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Sending...
                      </>
                    ) : (
                      'Resend Verification Email'
                    )}
                  </Button>

                  <Button
                    onClick={onSwitchToLogin}
                    variant="ghost"
                    className="w-full"
                  >
                    Back to Login
                  </Button>
                </div>

                <div className="text-center text-sm text-muted-foreground">
                  <p>After verifying your email, you can log in to access your account.</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Registration form
  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <Card>
          <CardHeader className="text-center">
            <CardTitle className="text-2xl">Create Account</CardTitle>
            <CardDescription>Sign up for Zoea Studio</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit}>
              <div className="flex flex-col gap-6">
                <div className="grid gap-2">
                  <Label htmlFor="username">Username</Label>
                  <Input
                    id="username"
                    name="username"
                    type="text"
                    value={formData.username}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    autoFocus
                    required
                    placeholder="Enter your username"
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    value={formData.email}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                    placeholder="Enter your email"
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="password1">Password</Label>
                  <Input
                    id="password1"
                    name="password1"
                    type="password"
                    value={formData.password1}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                    placeholder="Enter your password"
                  />
                  <p className="text-xs text-muted-foreground">
                    Must be at least 8 characters long
                  </p>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="password2">Confirm Password</Label>
                  <Input
                    id="password2"
                    name="password2"
                    type="password"
                    value={formData.password2}
                    onChange={handleChange}
                    disabled={isSubmitting}
                    required
                    placeholder="Re-enter your password"
                  />
                </div>

                {error && (
                  <div className="bg-destructive/10 border border-destructive text-destructive px-4 py-3 rounded-md text-sm">
                    {error}
                  </div>
                )}

                <Button type="submit" className="w-full" disabled={isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Creating account...
                    </>
                  ) : (
                    'Sign Up'
                  )}
                </Button>

                <div className="text-center text-sm">
                  <span className="text-muted-foreground">Already have an account? </span>
                  <button
                    type="button"
                    onClick={onSwitchToLogin}
                    className="text-primary hover:underline font-medium"
                  >
                    Sign in
                  </button>
                </div>
              </div>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default Register;
