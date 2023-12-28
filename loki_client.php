<?php

$host = "127.0.0.1";
$port = 1337;

$socket = @socket_create(AF_INET, SOCK_STREAM, 0);
$result = @socket_connect($socket, $host, $port);

$message = $argv[1];

if($result) {
    socket_write($socket, $message, strlen($message)) or die("Could not send data to server\n");
    $result = socket_read ($socket, 1024) or die("Could not read server response\n");
    echo $result;
} else {
    echo 'not connected';
}

echo "\n";

socket_close($socket);

?>