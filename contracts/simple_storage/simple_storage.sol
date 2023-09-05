// SPDX-License-Identifier: GPL-3.0
pragma solidity >=0.4.22 <0.9.0;

contract Sample {
    string public data;
    string public _backup;

    constructor() {
        data = "Hello, world!";
    }

    function setValue(string memory _data) public {
        data = _data;
    }

    function getValue() public view returns (string memory) {
        return data;
    }

    function backup() public {
        _backup = data;
    }

    function restore() public {
        data = _backup;
    }
}