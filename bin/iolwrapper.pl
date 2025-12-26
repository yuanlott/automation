#!/usr/bin/perl -w
use strict;
use Getopt::Long;
use IO::Socket;
use IO::Select;
use IO::Handle;
my @telnet_opts = (0xff, 0xfb, 0x01,
		   0xff, 0xfb, 0x03,
		   0xff, 0xfb, 0x00,
		   0xff, 0xfd, 0x00);
my $telopt = pack "C12", @telnet_opts;
my $connect_sock = 0;
my @ready;
my $user_input;
my $bytes;
my $kid = 0;
my $childpipe;
my $parentpipe;
my $handle;
my %opts = ();
$opts{'p'} = 10000;
GetOptions(\%opts, qw(m=s n=s p=i));
usage() if (!defined($opts{'m'}) || $opts{'p'} < 1024);
$opts{'n'} = $opts{'m'} if (!defined($opts{'n'}));
socketpair(CHILD,PARENT,AF_UNIX,SOCK_STREAM,PF_UNSPEC) || die "socketpair: $!";
CHILD->autoflush(1);
PARENT->autoflush(1);
$childpipe  = \*CHILD;
$parentpipe = \*PARENT;
$|=1;
my $listen_sock = IO::Socket::INET->new(Proto => 'tcp',
					LocalPort => $opts{'p'},
					Listen => 1,
					Reuse => 1);
die $@ unless $listen_sock;
my $selector = IO::Select->new() || die "Can't create Select object!\n";
$selector->add($listen_sock, $childpipe);
setupsig();
if (!defined($kid = fork)) {
    die "Can not fork: $!";
} elsif ($kid == 0) {
    	close CHILD;
	open(STDIN,  "<&PARENT");
	open(STDOUT, ">&PARENT");
	sleep 3;
	exec {$opts{'m'}} $opts{'n'}, @ARGV;
	die "Can not run $opts{'m'}: $!\n";
}
close PARENT;
print "\nParent ID is $$, Child ID is $kid.";
while (1) {
	my @ready = $selector->can_read;
	for $handle (@ready) {
		if ($handle eq $listen_sock) {
			$connect_sock = $listen_sock->accept();
			$selector->add($connect_sock);
			$selector->remove($listen_sock);
			$connect_sock->autoflush(1);
			syswrite($connect_sock, $telopt);
			sysread($connect_sock, $user_input, 80); 
		} elsif ($handle eq $connect_sock) {
			$bytes = sysread($handle, $user_input, 80);
			if ($bytes == 0) {
				$selector->add($listen_sock);
				$selector->remove($connect_sock);
				$connect_sock->shutdown(2);
				$connect_sock = 0;
			} else {
				syswrite(CHILD, $user_input);
			}
		} elsif ($handle eq $childpipe) {
			$bytes = sysread($handle, $user_input, 80);
			if ($bytes == 0) {
				close $connect_sock if ($connect_sock);
				close $listen_sock;
				exit(1);
			} else {
				if ($connect_sock) {
					syswrite($connect_sock, $user_input);
				} 
			}
		}
	}
}
sub setupsig {
	$SIG{INT}  = 'IGNORE';
	$SIG{TERM} = 'IGNORE';
	$SIG{HUP}  = 'IGNORE';
	$SIG{HUP}   = \&catch_sig_exit;
	$SIG{INT}   = \&catch_sig_exit;
	$SIG{HUP}   = \&catch_sig_exit;
	$SIG{KILL}  = \&catch_sig_exit;
	$SIG{CHLD}  = \&catch_sig_child;
}
sub catch_sig_exit {
	close $connect_sock if ($connect_sock);
	close $listen_sock  if ($listen_sock);
	kill(9, $kid) if ($kid);
	print STDERR "Killed child process $kid\n";
	exit 1;
}
sub catch_sig_child {
	close $connect_sock if ($connect_sock);
	sleep 1;
	print STDERR "Program $opts{'m'} with process ID $kid exit!\n";
	exit 1;
}
sub usage {
    print <<USAGE;

Usage: $0 -m <program> -p <port number> -n <name> -- [OPTIONS]

  -m <program>     Program will be wrappered, enter full path if needed.
  -p <port number> Port number to access the program, default is 10000.
  -n <name>        Process name for executed program, optional.
  [OPTIONS]        All the options/arguments passed to executed program.

USAGE
	exit;
}
